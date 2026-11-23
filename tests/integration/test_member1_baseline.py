"""Phase 1 Member 1: preserve access, error ordering, and commit-failure behavior."""

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import composition
from app.db.models import (
    MatchingRequestModel,
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.session import create_db_engine, create_session_factory
from app.features.auth import dependencies as auth_dependencies
from app.main import app


def database_snapshot(factory):
    # A fresh connection observes committed state, including timestamps and history.
    with factory() as db:
        return {
            model.__tablename__: db.execute(select(model.__table__).order_by(model.id)).all()
            for model in (
                UserModel,
                VenueModel,
                SessionModel,
                ParticipationModel,
                MatchingRequestModel,
            )
        }


@pytest.mark.parametrize(
    "command", ["register", "create", "cancel", "join", "approve", "reject", "withdraw"]
)
@pytest.mark.parametrize("failure", ["busy", "unexpected"])
def test_failed_commit_returns_error_and_preserves_database(
    client, auth_headers, game_data, db_session_factory, monkeypatch, command, failure
):
    host = auth_headers(game_data["host"])
    player = auth_headers(game_data["player"])
    participation_id = None
    if command in {"approve", "reject", "withdraw"}:
        pending = client.post(
            "/participations", headers=player, json={"session_id": game_data["first"]}
        )
        assert pending.status_code == 201, pending.text
        participation_id = pending.json()["id"]

    # Create/approve must roll back the matching closure as well as the booking.
    with db_session_factory() as db:
        game = db.get(SessionModel, game_data["first"])
        for actor in ("host", "player"):
            starts_at, ends_at = game.starts_at, game.ends_at
            if actor == "host":
                starts_at = datetime(2030, 11, 2, 12, tzinfo=timezone.utc)
                ends_at = datetime(2030, 11, 2, 14, tzinfo=timezone.utc)
            db.add(
                MatchingRequestModel(
                    user_id=game_data[actor],
                    venue_id=game_data["venue"],
                    starts_at=starts_at,
                    ends_at=ends_at,
                    play_type="SINGLES",
                    proposed_fee_male_vnd=60000,
                    proposed_fee_female_vnd=40000,
                    budget_max_vnd=60000,
                    gender_policy="ANY",
                    status="ACTIVE",
                    created_at=game.created_at,
                )
            )
        db.commit()
    before = database_snapshot(db_session_factory)
    attempts = []

    def fail_commit(db):
        db.flush()
        attempts.append(True)
        if failure == "busy":
            error = sqlite3.OperationalError("database is locked")
            error.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise OperationalError("COMMIT", {}, error)
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    if command == "register":
        response = client.post(
            "/auth/register",
            json={
                "email": "commit-test@example.com",
                "password": "test-password-123",
                "display_name": "Commit test",
                "skill_level": "TB",
                "gender": "MALE",
            },
        )
    elif command == "create":
        response = client.post(
            "/sessions",
            headers=host,
            json={
                "venue_id": game_data["venue"],
                "title": "Commit test",
                "starts_at": "2030-11-02T12:00:00Z",
                "ends_at": "2030-11-02T14:00:00Z",
                "play_type": "SINGLES",
                "fee_male_vnd": 60000,
                "fee_female_vnd": 40000,
                "min_level": "TB_MINUS",
                "max_level": "TB_PLUS",
            },
        )
    elif command == "cancel":
        response = client.delete(f"/sessions/{game_data['first']}", headers=host)
    elif command == "join":
        response = client.post(
            "/participations", headers=player, json={"session_id": game_data["first"]}
        )
    elif command in {"approve", "reject"}:
        response = client.post(
            f"/participations/{participation_id}/decision",
            headers=host,
            json={"decision": command.upper()},
        )
    else:
        response = client.delete(f"/participations/{participation_id}", headers=player)

    assert attempts == [True], response.text
    assert response.status_code == (503 if failure == "busy" else 500), response.text
    assert response.json()["error"]["code"] == (
        "DATABASE_BUSY" if failure == "busy" else "INTERNAL_ERROR"
    )
    if failure == "busy":
        assert response.headers["Retry-After"] == "1"
    assert "injected" not in response.text and "COMMIT" not in response.text
    assert database_snapshot(db_session_factory) == before


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/sessions"),
        ("GET", "/sessions/invalid"),
        ("DELETE", "/sessions/invalid"),
        ("POST", "/participations"),
        ("POST", "/participations/invalid/decision"),
        ("DELETE", "/participations/invalid"),
        ("POST", "/matching/requests"),
        ("GET", "/sessions?host_me=true&limit=invalid"),
    ],
)
def test_protected_routes_authenticate_before_payload_validation(client, method, path):
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "path,payload,expected",
    [
        ("/auth/register", {}, 422),
        ("/sessions", {}, 422),
        ("/participations", {}, 422),
        (
            "/auth/register",
            {
                "email": "locked@example.com",
                "password": "test-password-123",
                "display_name": "Lock test",
                "skill_level": "TB",
                "gender": "MALE",
            },
            503,
        ),
    ],
)
def test_payload_validation_priority_while_writer_is_locked(
    client, auth_headers, game_data, db_engine, monkeypatch, path, payload, expected
):
    contender = create_db_engine(str(db_engine.url), busy_timeout=20)
    try:
        factory = create_session_factory(contender)
        for module in (auth_dependencies, composition):
            monkeypatch.setattr(module, "_session_factory", factory)
        with db_engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            response = client.post(path, json=payload, headers=auth_headers(game_data["player"]))
            assert response.status_code == expected, response.text
            assert response.json()["error"]["code"] == (
                "DATABASE_BUSY" if expected == 503 else "VALIDATION_ERROR"
            )
            blocker.rollback()
    finally:
        contender.dispose()


def test_detail_exposes_only_the_viewers_participations_to_non_hosts(
    client, auth_headers, game_data
):
    player = auth_headers(game_data["player"])
    payload = {"session_id": game_data["first"]}
    pending = client.post(
        "/participations",
        headers=player,
        json=payload,
    )
    assert pending.status_code == 201, pending.text
    withdrawn = client.delete(f"/participations/{pending.json()['id']}", headers=player)
    assert withdrawn.status_code == 200, withdrawn.text
    rejoined = client.post("/participations", headers=player, json=payload)
    assert rejoined.status_code == 201, rejoined.text

    def unexpected_command_service():
        pytest.fail("Session detail must use the read service")

    app.dependency_overrides[composition.provide_session_service] = unexpected_command_service
    for actor in ("host", "player", "other"):
        response = client.get(
            f"/sessions/{game_data['first']}", headers=auth_headers(game_data[actor])
        )
        assert response.status_code == 200, response.text
        data = response.json()
        participations = data["my_participations"]
        assert all(row["user_id"] == game_data[actor] for row in participations)
        if actor == "host":
            assert [row["status"] for row in participations] == ["ACCEPTED"]
            assert len(data["management"]["participations"]) == 3
        else:
            assert data["management"] is None
            expected = {"PENDING", "CANCELLED"} if actor == "player" else set()
            assert {row["status"] for row in participations} == expected
        assert "password_hash" not in response.text and "email" not in response.text


@pytest.mark.parametrize(
    "email,password",
    [
        ("login-test@example.com", "wrong-password"),
        ("unknown@example.com", "test-password-123"),
    ],
)
def test_invalid_login_has_the_same_response_for_unknown_user_and_wrong_password(
    client, email, password
):
    registered = client.post(
        "/auth/register",
        json={
            "email": "login-test@example.com",
            "password": "test-password-123",
            "display_name": "Login test",
            "skill_level": "TB",
            "gender": "MALE",
        },
    )
    assert registered.status_code == 201, registered.text
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_login_payload_returns_validation_error(client):
    response = client.post("/auth/login", json={"email": "invalid", "password": "secret"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "secret" not in response.text
