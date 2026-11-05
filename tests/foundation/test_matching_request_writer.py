from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.models import MatchingRequestModel, VenueModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork

START = datetime(2030, 11, 1, 12, tzinfo=timezone.utc)
NOW = START - timedelta(hours=1)


def add_request(session, data, user="player", status="ACTIVE", start=START, end=None):
    request = MatchingRequestModel(
        user_id=data[user],
        venue_id=data["venue"],
        starts_at=start,
        ends_at=end or start + timedelta(hours=2),
        play_type="DOUBLES",
        proposed_fee_male_vnd=60000,
        proposed_fee_female_vnd=40000,
        budget_max_vnd=80000,
        gender_policy="ANY",
        status=status,
        created_at=NOW,
        closed_reason="REPLACED" if status == "CLOSED" else None,
        closed_at=NOW if status == "CLOSED" else None,
    )
    session.add(request)
    session.flush()
    return request.id


@pytest.fixture
def request_id(db_session_factory, game_data):
    with db_session_factory() as session:
        request_id = add_request(session, game_data)
        session.commit()
        return request_id


def make_uow(factory):
    return SqlAlchemyUnitOfWork(factory, lambda: RuntimeError("DATABASE_BUSY"))


def test_closes_active_overlap(db_session_factory, game_data, request_id):
    uow = make_uow(db_session_factory)
    with uow.write():
        SqlAlchemyMatchingRequestWriter(lambda: uow.session).close_overlapping(
            game_data["player"],
            START + timedelta(minutes=30),
            START + timedelta(hours=3),
            NOW,
        )
        uow.commit()
    with db_session_factory() as session:
        saved = session.get(MatchingRequestModel, request_id)
        assert (saved.status, saved.closed_reason, saved.closed_at) == ("CLOSED", "CONFIRMED", NOW)


@pytest.mark.parametrize("offset", [-2, 2])
def test_adjacent_does_not_close(db_session_factory, game_data, request_id, offset):
    uow = make_uow(db_session_factory)
    with uow.write():
        SqlAlchemyMatchingRequestWriter(lambda: uow.session).close_overlapping(
            game_data["player"],
            START + timedelta(hours=offset),
            START + timedelta(hours=offset + 2),
            NOW,
        )
        uow.commit()
    with db_session_factory() as session:
        assert session.get(MatchingRequestModel, request_id).status == "ACTIVE"


def test_keeps_other_user_and_closed_history(db_session_factory, game_data):
    with db_session_factory() as session:
        other_id = add_request(session, game_data, user="other")
        history_id = add_request(session, game_data, status="CLOSED")
        session.commit()
    uow = make_uow(db_session_factory)
    with uow.write():
        SqlAlchemyMatchingRequestWriter(lambda: uow.session).close_overlapping(
            game_data["player"],
            START,
            START + timedelta(hours=2),
            NOW,
        )
        uow.commit()
    with db_session_factory() as session:
        assert session.get(MatchingRequestModel, other_id).status == "ACTIVE"
        assert session.get(MatchingRequestModel, history_id).closed_reason == "REPLACED"


def test_missing_commit_rolls_back(db_session_factory, game_data, request_id):
    uow = make_uow(db_session_factory)
    with uow.write():
        SqlAlchemyMatchingRequestWriter(lambda: uow.session).close_overlapping(
            game_data["player"],
            START,
            START + timedelta(hours=2),
            NOW,
        )
    with db_session_factory() as session:
        assert session.get(MatchingRequestModel, request_id).status == "ACTIVE"


def test_writer_and_other_change_roll_back_together(db_session_factory, game_data, request_id):
    uow = make_uow(db_session_factory)
    with pytest.raises(ValueError, match="stop"):
        with uow.write():
            SqlAlchemyMatchingRequestWriter(lambda: uow.session).close_overlapping(
                game_data["player"],
                START,
                START + timedelta(hours=2),
                NOW,
            )
            uow.session.get(VenueModel, game_data["venue"]).name = "Đổi rồi rollback"
            uow.session.flush()
            raise ValueError("stop")
    with db_session_factory() as session:
        assert session.get(MatchingRequestModel, request_id).status == "ACTIVE"
        assert session.scalar(select(VenueModel.name)) == "Sân test"
