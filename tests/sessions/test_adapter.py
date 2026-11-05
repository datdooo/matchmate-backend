from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import ParticipationModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.entities import Participation
from app.domain.enums import Gender, ParticipationStatus
from app.domain.errors import DomainError
from app.features.sessions.participation_contracts import CreateParticipationInput
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository

NOW = datetime(2030, 11, 1, 10, tzinfo=timezone.utc)


@pytest.fixture
def adapter(db_session_factory):
    uow = SqlAlchemyUnitOfWork(db_session_factory, lambda: RuntimeError("DATABASE_BUSY"))
    return uow, SqlAlchemyParticipationRepository(lambda: uow.session)


def new_input(data, **changes):
    values = dict(
        user_id=data["player"],
        session_id=data["first"],
        gender_at_join=Gender.FEMALE,
        quoted_fee_vnd=40000,
    )
    return CreateParticipationInput(**(values | changes))


def test_create_and_detail_return_plain_data(adapter, game_data):
    uow, repo = adapter
    with uow.write():
        saved = repo.create(new_input(game_data), NOW)
        detail = repo.detail(saved.id, game_data["player"], NOW)
        records = repo.list_for_session(
            game_data["first"], actor_user_id=game_data["host"], now=NOW
        )
        uow.commit()
    assert isinstance(saved, Participation)
    assert saved.status == ParticipationStatus.PENDING
    assert saved.gender_at_join == Gender.FEMALE
    assert detail.can_cancel and not detail.can_decide
    assert detail.session.host.id == game_data["host"]
    assert detail.session.venue.district_code == "CAU_GIAY"
    assert (detail.session.accepted_count, detail.session.remaining_capacity) == (1, 3)
    assert [record.can_decide for record in records] == [False, True]
    assert saved.decided_at is None and saved.cancelled_at is None


@pytest.mark.parametrize(
    "target",
    [ParticipationStatus.ACCEPTED, ParticipationStatus.REJECTED, ParticipationStatus.CANCELLED],
)
def test_status_keeps_snapshot_and_sets_correct_timestamp(adapter, game_data, target):
    uow, repo = adapter
    later = NOW + timedelta(minutes=1)
    with uow.write():
        first = repo.create(new_input(game_data), NOW)
        saved = repo.set_status(first.id, target, later)
        uow.commit()
    assert (saved.quoted_fee_vnd, saved.gender_at_join, saved.created_at) == (
        40000,
        Gender.FEMALE,
        NOW,
    )
    assert saved.decided_at == (None if target == ParticipationStatus.CANCELLED else later)
    assert saved.cancelled_at == (later if target == ParticipationStatus.CANCELLED else None)


def test_only_active_unique_maps_to_business_error(adapter, game_data, db_session_factory):
    uow, repo = adapter
    with pytest.raises(DomainError, match="Đã có lượt") as caught:
        with uow.write():
            repo.create(new_input(game_data), NOW)
            repo.create(new_input(game_data), NOW)
    assert caught.value.code == "PARTICIPATION_ALREADY_EXISTS"
    with db_session_factory() as session:
        assert (
            session.scalar(
                select(ParticipationModel).where(ParticipationModel.user_id == game_data["player"])
            )
            is None
        )
    # FK không được biến thành lỗi trùng lượt.
    with pytest.raises(IntegrityError):
        with uow.write():
            repo.create(new_input(game_data, session_id=9999), NOW)


def test_cancel_active_keeps_history_and_allows_new_record(adapter, game_data):
    uow, repo = adapter
    with uow.write():
        old = repo.create(new_input(game_data), NOW)
        repo.set_status(old.id, ParticipationStatus.REJECTED, NOW)
        pending = repo.create(new_input(game_data), NOW)
        repo.cancel_active_for_session(game_data["first"], NOW)
        assert repo.get_by_id(old.id).status == ParticipationStatus.REJECTED
        assert repo.get_by_id(pending.id).status == ParticipationStatus.CANCELLED
        assert repo.count_accepted(game_data["first"]) == 0  # gồm cả host
        assert len(repo.list_for_session(game_data["first"])) == 3
        uow.commit()


def test_no_commit_rolls_back_and_callback_requires_active_uow(adapter, game_data):
    uow, repo = adapter
    with pytest.raises(RuntimeError, match="No active"):
        repo.count_accepted(game_data["first"])
    with uow.write():
        created = repo.create(new_input(game_data), NOW)
    with uow.read():
        assert repo.get_by_id(created.id) is None
        assert repo.get_session(9999) is None
        assert repo.list_for_session(9999) == []
