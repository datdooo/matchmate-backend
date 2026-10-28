from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.db.models import ParticipationModel, SessionModel, UserModel, VenueModel
from app.features.auth.security import Argon2PasswordHasher
from scripts.run_kaggle_load_test import check_invariants, missing_routes, prepare_dataset
from scripts.seed_load_data import TEST_PASSWORD


@pytest.mark.parametrize("users", [10, 100])
def test_load_dataset_has_required_boundaries_and_separate_actors(db_engine, users):
    now = datetime(2030, 11, 1, tzinfo=timezone.utc)
    manifest = prepare_dataset(db_engine, users, now)
    assert len(manifest["session_ids"]) == 30 and len(manifest["venue_ids"]) == 10
    assert len(manifest["read"]) == users and len(manifest["pairs"]) == users
    actors = [entry[role]["email"] for entry in manifest["pairs"] for role in ("host", "player")]
    assert len(set(actors)) == 2 * users
    assert not set(actors) & {entry["email"] for entry in manifest["read"]}
    with db_engine.connect() as connection:
        games = connection.execute(select(SessionModel.__table__)).mappings().all()
        assert sum(game["play_type"] == "DOUBLES" for game in games) == 21
        assert sum(game["play_type"] == "SINGLES" for game in games) == 9
        durations = {(game["ends_at"] - game["starts_at"]).total_seconds() / 60 for game in games}
        assert {60, 240} <= durations
        assert any(game["fee_male_vnd"] == game["fee_female_vnd"] == 0 for game in games)
        assert all(game["starts_at"] > now for game in games)
        assert connection.scalar(select(func.count()).select_from(ParticipationModel)) == 30
        assert connection.scalar(select(func.count()).select_from(VenueModel)) == 10
        password_hash = connection.scalar(select(UserModel.password_hash).limit(1))
    assert Argon2PasswordHasher().verify(TEST_PASSWORD, password_hash)
    assert not any(check_invariants(db_engine).values())


def test_load_preflight_names_missing_business_routes():
    schema = {"paths": {"/health": {"get": {}}, "/auth/register": {"post": {}}}}
    missing = set(missing_routes(schema))
    assert ("get", "/venues") in missing
    assert ("get", "/sessions/{session_id}") in missing
    assert ("delete", "/sessions/{session_id}") in missing
    assert ("post", "/participations/{participation_id}/decision") in missing
    assert ("post", "/matching/requests") in missing
    assert ("post", "/auth/register") not in missing


def test_invariant_detector_catches_capacity(db_session_factory, db_engine, game_data):
    with db_session_factory() as session:
        game = session.get(SessionModel, game_data["first"])
        game.play_type = "SINGLES"
        for actor in ("player", "other"):
            session.add(
                ParticipationModel(
                    user_id=game_data[actor],
                    session_id=game.id,
                    status="ACCEPTED",
                    gender_at_join="MALE",
                    quoted_fee_vnd=0,
                    created_at=game.created_at,
                    decided_at=game.created_at,
                )
            )
        session.commit()
    assert check_invariants(db_engine)["over_capacity"] == 1


def test_invariant_detector_catches_overlap_and_incomplete_cancel(
    db_session_factory, db_engine, game_data
):
    with db_session_factory() as session:
        first = session.get(SessionModel, game_data["first"])
        second = session.get(SessionModel, game_data["second"])
        second.starts_at = first.starts_at + timedelta(minutes=30)
        first.status, first.cancelled_at = "CANCELLED", first.created_at
        session.commit()
    result = check_invariants(db_engine)
    assert result["accepted_overlap"] == 1 and result["active_in_cancelled"] == 1
