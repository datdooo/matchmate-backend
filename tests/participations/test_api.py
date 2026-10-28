import pytest
from sqlalchemy import select

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.models import MatchingRequestModel, ParticipationModel, SessionModel
from app.db.session import create_db_engine, create_session_factory
from app.features.sessions.participation_dependencies import provide_participation_service
from app.main import app


def test_actual_routes_with_jwt_and_full_response(client, auth_headers, game_data):
    player = auth_headers(game_data["player"])
    host = auth_headers(game_data["host"])
    response = client.post(
        "/participations", json={"session_id": game_data["first"]}, headers=player
    )
    assert response.status_code == 201, response.text
    record = response.json()
    assert set(record) == {
        "id",
        "user_id",
        "session_id",
        "player",
        "status",
        "created_at",
        "decided_at",
        "cancelled_at",
        "can_cancel",
        "can_decide",
        "gender_at_join",
        "quoted_fee_vnd",
        "session",
    }
    assert record["decided_at"] is None and record["cancelled_at"] is None
    assert record["player"]["skill_level"] == "TB"
    assert record["session"]["min_level"] == "TB_MINUS"
    assert record["session"]["max_level"] == "TB_PLUS"
    assert record["session"]["host"]["id"] == game_data["host"]
    assert record["created_at"].endswith("Z")
    assert set(record["session"]["venue"]) == {
        "id",
        "name",
        "address",
        "district_code",
        "is_active",
    }
    route = f"/participations/{record['id']}"
    approved = client.post(route + "/decision", json={"decision": "APPROVE"}, headers=host)
    assert approved.status_code == 200, approved.text
    assert approved.json()["session"]["accepted_count"] == 2
    assert approved.json()["can_decide"] is False
    withdrawn = client.delete(route, headers=player)
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "CANCELLED"
    assert withdrawn.json()["session"]["remaining_capacity"] == 3
    assert client.delete(route, headers=player).json() == withdrawn.json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"session_id": None},
        {"session_id": True},
        {"session_id": 1.0},
        {"session_id": "1"},
        {"session_id": 0},
        {"session_id": -1},
        {"session_id": 2**63},
        {"session_id": 1, "user_id": 2},
        {"session_id": 1, "quoted_fee_vnd": 0},
    ],
)
def test_join_body_is_strict(client, auth_headers, game_data, payload):
    response = client.post(
        "/participations", json=payload, headers=auth_headers(game_data["player"])
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("decision", ["APPROVED", "approve", "", None, True, 1])
def test_decision_is_strict(client, auth_headers, game_data, decision):
    response = client.post(
        "/participations/1/decision",
        json={"decision": decision},
        headers=auth_headers(game_data["host"]),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("identifier", ["0", "-1", "1.5", "abc", str(2**63)])
def test_path_id_is_positive_sqlite_integer(client, auth_headers, game_data, identifier):
    assert (
        client.delete(
            f"/participations/{identifier}", headers=auth_headers(game_data["player"])
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/participations", {"session_id": 1}),
        ("POST", "/participations/1/decision", {"decision": "APPROVE"}),
        ("DELETE", "/participations/1", None),
    ],
)
def test_all_three_routes_require_jwt(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_error_mapping_and_envelope(client, auth_headers, game_data):
    player = auth_headers(game_data["player"])
    response = client.post("/participations", json={"session_id": 9999}, headers=player)
    assert response.status_code == 404 and response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    created = client.post(
        "/participations", json={"session_id": game_data["first"]}, headers=player
    )
    part_id = created.json()["id"]
    duplicate = client.post(
        "/participations", json={"session_id": game_data["first"]}, headers=player
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PARTICIPATION_ALREADY_EXISTS"
    forbidden = client.post(
        f"/participations/{part_id}/decision", json={"decision": "APPROVE"}, headers=player
    )
    assert forbidden.status_code == 403 and forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert forbidden.headers["X-Request-ID"] == forbidden.json()["error"]["request_id"]
    # Method sai vẫn giữ 405 và Allow, không biến thành domain error.
    wrong_method = client.put(f"/participations/{part_id}")
    assert wrong_method.status_code == 405 and "DELETE" in wrong_method.headers["Allow"]


def test_real_lock_timeout_returns_503(
    client, auth_headers, game_data, db_engine, make_service, db_session_factory
):
    contender = create_db_engine(str(db_engine.url), busy_timeout=20)
    factory = create_session_factory(contender)
    app.dependency_overrides[provide_participation_service] = lambda: make_service(factory=factory)
    try:
        with db_engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            response = client.post(
                "/participations",
                json={"session_id": game_data["first"]},
                headers=auth_headers(game_data["player"]),
            )
            assert response.status_code == 503
            assert response.headers["Retry-After"] == "1"
            assert response.json()["error"]["code"] == "DATABASE_BUSY"
            blocker.rollback()
        with db_session_factory() as session:
            assert (
                session.scalar(
                    select(ParticipationModel).where(
                        ParticipationModel.user_id == game_data["player"]
                    )
                )
                is None
            )
    finally:
        contender.dispose()


def test_register_login_create_join_approve_withdraw(client, db_session_factory, game_data):
    tokens = []
    for name, gender in [("newhost", "MALE"), ("newplayer", "FEMALE")]:
        payload = dict(
            email=f"{name}@example.com",
            password="test-password-123",
            display_name=name,
            skill_level="TB",
            gender=gender,
        )
        assert client.post("/auth/register", json=payload).status_code == 201
        login = client.post(
            "/auth/login", json={"email": payload["email"], "password": payload["password"]}
        )
        assert login.status_code == 200, login.text
        tokens.append({"Authorization": "Bearer " + login.json()["access_token"]})
    game = client.post(
        "/sessions",
        headers=tokens[0],
        json={
            "venue_id": game_data["venue"],
            "title": "Kèo kiểm thử toàn luồng",
            "starts_at": "2030-11-02T19:00:00+07:00",
            "ends_at": "2030-11-02T21:00:00+07:00",
            "play_type": "SINGLES",
            "fee_male_vnd": 60000,
            "fee_female_vnd": 40000,
            "min_level": "TB_MINUS",
            "max_level": "TB_PLUS",
        },
    )
    assert game.status_code == 201, game.text
    pending = client.post(
        "/participations", json={"session_id": game.json()["id"]}, headers=tokens[1]
    )
    assert pending.status_code == 201, pending.text
    route = f"/participations/{pending.json()['id']}"
    approved = client.post(route + "/decision", json={"decision": "APPROVE"}, headers=tokens[0])
    assert approved.status_code == 200 and approved.json()["session"]["remaining_capacity"] == 0
    assert client.delete(route, headers=tokens[1]).status_code == 200


def test_check_failure_rolls_back_approval_and_matching(
    client, service, auth_headers, game_data, db_session_factory, clock, monkeypatch
):
    pending = service.join(game_data["player"], game_data["first"])
    with db_session_factory() as session:
        game = session.get(SessionModel, game_data["first"])
        request = MatchingRequestModel(
            user_id=game_data["player"],
            venue_id=game_data["venue"],
            starts_at=game.starts_at,
            ends_at=game.ends_at,
            play_type="DOUBLES",
            proposed_fee_male_vnd=60000,
            proposed_fee_female_vnd=40000,
            budget_max_vnd=80000,
            gender_policy="ANY",
            status="ACTIVE",
            created_at=clock.value,
        )
        session.add(request)
        session.commit()
        request_id = request.id
    close = SqlAlchemyMatchingRequestWriter.close_overlapping

    def fail_after_close(self, *args):
        close(self, *args)
        # Ép lỗi CHECK thật sau hai cập nhật, thay vì chỉ ném exception giả.
        self._session_provider().connection().exec_driver_sql("UPDATE venues SET is_active = 2")

    monkeypatch.setattr(SqlAlchemyMatchingRequestWriter, "close_overlapping", fail_after_close)
    response = client.post(
        f"/participations/{pending.id}/decision",
        json={"decision": "APPROVE"},
        headers=auth_headers(game_data["host"]),
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "CHECK" not in response.text and "UPDATE" not in response.text
    with db_session_factory() as session:
        assert session.get(ParticipationModel, pending.id).status == "PENDING"
        assert session.get(MatchingRequestModel, request_id).status == "ACTIVE"
