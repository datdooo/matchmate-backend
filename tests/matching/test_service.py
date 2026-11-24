from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.db.models import MatchingRequestModel, UserModel, VenueModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.enums import Gender, GenderPolicy, PlayType, rank_to_skill
from app.domain.errors import DatabaseBusyError, DomainError
from app.features.auth.infrastructure.player_profile_reader import SqlAlchemyPlayerProfileReader
from app.features.catalog.venue_reader import SqlAlchemyVenueStatusReader
from app.features.matching.contracts import CreateMatchingInput
from app.features.matching.repository import SqlAlchemyMatchingRepository
from app.features.matching.service import MatchingService
from app.features.matching.strategy import find_group

NOW = datetime(2030, 11, 2, 10, tzinfo=timezone.utc)
DATA = CreateMatchingInput(
    venue_id=10,
    starts_at=NOW + timedelta(hours=2),
    ends_at=NOW + timedelta(hours=4),
    play_type=PlayType.SINGLES,
    proposed_fee_male_vnd=60_000,
    proposed_fee_female_vnd=40_000,
    budget_max_vnd=60_000,
    gender_policy=GenderPolicy.ANY,
)


@pytest.fixture
def matching_data(db_session_factory):
    with db_session_factory.begin() as db:
        db.add(VenueModel(id=10, name="Sân", address="Địa chỉ", district_code="CAU_GIAY"))
        for user_id in (100, 201, 211):
            db.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.invalid",
                    password_hash="fixture",
                    display_name=f"P{user_id}",
                    skill_level=9,
                    gender="MALE",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        db.flush()
        for request_id, user_id in ((900, 100), (200, 201), (210, 211)):
            db.add(
                MatchingRequestModel(
                    id=request_id,
                    user_id=user_id,
                    venue_id=10,
                    starts_at=DATA.starts_at,
                    ends_at=DATA.ends_at,
                    play_type="SINGLES",
                    proposed_fee_male_vnd=60_000,
                    proposed_fee_female_vnd=40_000,
                    budget_max_vnd=60_000,
                    gender_policy="ANY",
                    status="ACTIVE",
                    created_at=NOW - timedelta(minutes=1),
                )
            )


def build(factory, *, rewrite=None, strategy=find_group):
    uow = SqlAlchemyUnitOfWork(factory, DatabaseBusyError)
    profiles = SqlAlchemyPlayerProfileReader(lambda: uow.session)
    batch = Mock(wraps=profiles)
    if rewrite is not None:
        batch.get_by_ids.side_effect = lambda ids: rewrite(profiles.get_by_ids(ids))
    repo = SqlAlchemyMatchingRepository(uow)
    service = MatchingService(
        uow=uow,
        clock=SimpleNamespace(now=lambda: NOW),
        matching_repo=repo,
        profile_reader=profiles,
        profiles_reader=batch,
        venues=SqlAlchemyVenueStatusReader(lambda: uow.session),
        strategy=strategy,
    )
    return service, uow, repo, profiles, batch


@pytest.mark.parametrize(
    "mode,expected", [("missing", 211), ("unspecified", 211), ("rank", 211), ("reverse", 201)]
)
def test_batch_enrichment_preserves_request_order_and_filters_profiles(
    db_session_factory, matching_data, mode, expected
):
    def rewrite(profiles):
        if mode == "missing":
            profiles.pop(201)
        elif mode == "unspecified":
            profiles[201] = replace(profiles[201], gender=Gender.UNSPECIFIED)
        elif mode == "rank":
            profiles[201] = replace(profiles[201], skill_level=rank_to_skill(12))
        return dict(reversed(list(profiles.items())))

    service, _, _, _, batch = build(db_session_factory, rewrite=rewrite)
    result = service.create_matching_request(100, DATA)
    assert [member.id for member in result.suggestion.members] == [100, expected]
    assert result.suggestion.members[0].skill_level == 9
    batch.get_by_ids.assert_called_once_with([201, 211])


@pytest.mark.parametrize("point", ["create", "candidates", "profiles", "strategy", "commit"])
def test_failure_after_replacement_rolls_back_new_request_and_keeps_old(
    db_session_factory, matching_data, monkeypatch, point
):
    service, uow, repo, _, batch = build(db_session_factory)

    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")

    if point in ("create", "candidates"):
        monkeypatch.setattr(repo, point, fail)
    elif point == "profiles":
        batch.get_by_ids.side_effect = fail
    elif point == "strategy":
        service._strategy = fail
    else:
        monkeypatch.setattr(uow, "commit", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        service.create_matching_request(100, DATA)
    with db_session_factory() as db:
        requests = db.scalars(
            select(MatchingRequestModel).where(MatchingRequestModel.user_id == 100)
        ).all()
        assert [(r.id, r.status, r.closed_reason) for r in requests] == [(900, "ACTIVE", None)]


@pytest.mark.parametrize(
    "state,code", [("missing", "UNAUTHORIZED"), ("unspecified", "PROFILE_INCOMPLETE")]
)
def test_caller_profile_errors_keep_existing_request(
    db_session_factory, matching_data, monkeypatch, state, code
):
    service, _, _, profiles, _ = build(db_session_factory)
    actual = profiles.get_by_id
    monkeypatch.setattr(
        profiles,
        "get_by_id",
        lambda uid: None if state == "missing" else replace(actual(uid), gender=Gender.UNSPECIFIED),
    )
    with pytest.raises(DomainError) as raised:
        service.create_matching_request(100, DATA)
    assert raised.value.code == code


@pytest.mark.parametrize(
    "venue_id,active,code", [(999, True, "VENUE_NOT_FOUND"), (10, False, "VENUE_INACTIVE")]
)
def test_catalog_errors_are_preserved(db_session_factory, matching_data, venue_id, active, code):
    if not active:
        with db_session_factory.begin() as db:
            db.get(VenueModel, 10).is_active = False
    service, *_ = build(db_session_factory)
    with pytest.raises(DomainError) as raised:
        service.create_matching_request(100, replace(DATA, venue_id=venue_id))
    assert raised.value.code == code


def test_strategy_can_be_replaced_in_composition_without_changing_router(
    client, auth_headers, db_session_factory, matching_data, monkeypatch
):
    from app import composition

    alternative = Mock(return_value=None)
    monkeypatch.setattr(composition, "find_group", alternative)
    monkeypatch.setattr(composition, "SystemClock", lambda: SimpleNamespace(now=lambda: NOW))
    payload = {field: getattr(DATA, field) for field in DATA.__dataclass_fields__}
    payload.update(starts_at=DATA.starts_at.isoformat(), ends_at=DATA.ends_at.isoformat())
    response = client.post("/matching/requests", headers=auth_headers(100), json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["suggestion"] is None
    alternative.assert_called_once()


def test_session_creation_writer_failure_rolls_back_session_and_matching(
    client, auth_headers, db_session_factory, matching_data, monkeypatch
):
    from app.db.models import SessionModel
    from app.features.matching.matching_request_writer import (
        SqlAlchemyMatchingRequestWriter,
    )

    original = SqlAlchemyMatchingRequestWriter.close_overlapping

    def fail_after_close(self, *args):
        original(self, *args)
        raise RuntimeError("writer failure after close")

    monkeypatch.setattr(SqlAlchemyMatchingRequestWriter, "close_overlapping", fail_after_close)
    response = client.post(
        "/sessions",
        headers=auth_headers(100),
        json={
            "venue_id": 10,
            "title": "Rollback",
            "starts_at": DATA.starts_at.isoformat(),
            "ends_at": DATA.ends_at.isoformat(),
            "play_type": "SINGLES",
            "fee_male_vnd": 60_000,
            "fee_female_vnd": 40_000,
            "min_level": "TB_MINUS",
            "max_level": "TB_PLUS",
        },
    )
    assert response.status_code == 500
    with db_session_factory() as db:
        assert db.scalars(select(SessionModel)).all() == []
        assert db.get(MatchingRequestModel, 900).status == "ACTIVE"
