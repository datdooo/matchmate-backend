"""Các route đã ghép phải chạy qua SQLite thật, không chỉ test mapper/fake service."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import MatchingRequestModel, ParticipationModel, UserModel
from app.features.sessions import session_router


def matching_payload(venue_id):
    return {
        "venue_id": venue_id,
        "starts_at": "2030-11-02T12:00:00Z",
        "ends_at": "2030-11-02T14:00:00Z",
        "play_type": "SINGLES",
        "proposed_fee_male_vnd": 60000,
        "proposed_fee_female_vnd": 40000,
        "budget_max_vnd": 60000,
    }


def test_public_discovery_returns_full_dtos_and_level_names(client, game_data, auth_headers):
    assert client.get("/sessions", params={"host_me": "true"}).status_code == 401
    venues = client.get("/venues", params={"district_code": "CAU_GIAY"})
    assert venues.status_code == 200, venues.text
    assert venues.json()["items"][0]["id"] == game_data["venue"]
    games = client.get(
        "/sessions",
        params={"district_code": "CAU_GIAY", "skill_level": "TB", "max_fee_vnd": 60000},
    )
    assert games.status_code == 200, games.text
    assert games.json()["total"] == 2
    first = games.json()["items"][0]
    assert first["host"]["skill_level"] == "TB" and "email" not in first["host"]
    assert first["venue"]["district_code"] == "CAU_GIAY"
    assert (first["min_level"], first["max_level"]) == ("TB_MINUS", "TB_PLUS")
    detail = client.get(f"/sessions/{first['id']}", headers=auth_headers(game_data["player"]))
    assert detail.status_code == 200, detail.text
    assert {key: detail.json()[key] for key in first} == first
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/matching/requests"]["post"]["security"] == [{"HTTPBearer": []}]


def test_matching_replace_group_create_approve_cancel(
    client, auth_headers, game_data, db_session_factory
):
    player, host = auth_headers(game_data["player"]), auth_headers(game_data["host"])
    payload = matching_payload(game_data["venue"])
    first = client.post("/matching/requests", json=payload, headers=player)
    assert first.status_code == 201, first.text
    assert first.json()["suggestion"] is None
    replacement = client.post("/matching/requests", json=payload, headers=player)
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["request"]["id"] != first.json()["request"]["id"]
    grouped = client.post("/matching/requests", json=payload, headers=host)
    assert grouped.status_code == 201, grouped.text
    members = grouped.json()["suggestion"]["members"]
    assert len(members) == 2 and all(member["skill_level"] == "TB" for member in members)
    assert {member["estimated_fee_vnd"] for member in members} == {40000, 60000}
    assert all("email" not in member and "budget_max_vnd" not in member for member in members)

    game = client.post(
        "/sessions",
        headers=host,
        json={
            "venue_id": payload["venue_id"],
            "title": "Kèo từ nhóm matching",
            "starts_at": payload["starts_at"],
            "ends_at": payload["ends_at"],
            "play_type": "SINGLES",
            "fee_male_vnd": 60000,
            "fee_female_vnd": 40000,
            "min_level": "TB_MINUS",
            "max_level": "TB_PLUS",
        },
    )
    assert game.status_code == 201, game.text
    pending = client.post("/participations", json={"session_id": game.json()["id"]}, headers=player)
    assert pending.status_code == 201, pending.text
    part_id = pending.json()["id"]
    approved = client.post(
        f"/participations/{part_id}/decision", json={"decision": "APPROVE"}, headers=host
    )
    assert approved.status_code == 200, approved.text
    with db_session_factory() as db:
        requests = db.scalars(select(MatchingRequestModel).order_by(MatchingRequestModel.id)).all()
        assert [request.closed_reason for request in requests] == [
            "REPLACED",
            "CONFIRMED",
            "CONFIRMED",
        ]
    cancelled = client.delete(f"/sessions/{game.json()['id']}", headers=host)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["accepted_count"] == 0
    assert client.delete(f"/participations/{part_id}", headers=player).status_code == 200


def test_cancel_preserves_history_and_checks_owner_before_idempotency(
    client, auth_headers, game_data, db_session_factory, monkeypatch
):
    host, player = auth_headers(game_data["host"]), auth_headers(game_data["player"])
    route = f"/sessions/{game_data['first']}"
    assert client.delete(route, headers=player).status_code == 403
    for actor in ("player", "other"):
        headers = auth_headers(game_data[actor])
        pending = client.post(
            "/participations", headers=headers, json={"session_id": game_data["first"]}
        )
        assert pending.status_code == 201, pending.text
        decision = "APPROVE" if actor == "player" else "REJECT"
        assert (
            client.post(
                f"/participations/{pending.json()['id']}/decision",
                headers=host,
                json={"decision": decision},
            ).status_code
            == 200
        )
    again = client.post(
        "/participations",
        headers=auth_headers(game_data["other"]),
        json={"session_id": game_data["first"]},
    )
    assert again.status_code == 201, again.text
    cancelled = client.delete(route, headers=host)
    assert cancelled.status_code == 200, cancelled.text
    with db_session_factory() as db:
        rows = db.scalars(
            select(ParticipationModel).where(ParticipationModel.session_id == game_data["first"])
        ).all()
        assert sorted(row.status for row in rows) == [
            "CANCELLED",
            "CANCELLED",
            "CANCELLED",
            "REJECTED",
        ]
        assert all(row.cancelled_at is None for row in rows if row.status == "REJECTED")
    # DELETE lặp sau starts_at vẫn trả bản cũ, nhưng người khác vẫn không được hủy.
    monkeypatch.setattr(
        session_router,
        "SystemClock",
        lambda: SimpleNamespace(now=lambda: datetime(2035, 1, 1, tzinfo=timezone.utc)),
    )
    assert client.delete(route, headers=host).json() == cancelled.json()
    assert client.delete(route, headers=player).status_code == 403
    assert client.get("/sessions", headers=host, params={"host_me": "true"}).status_code == 200


@pytest.mark.parametrize(
    "path,changes",
    [
        ("/sessions", {"venue_id": 2**63}),
        ("/venues", {"offset": 2**63}),
        ("/matching/requests", {"venue_id": 2**63}),
        ("/matching/requests", {"proposed_fee_male_vnd": 2**63}),
        ("/matching/requests", {"starts_at": 1919851200, "ends_at": 1919858400}),
        ("/matching/requests", {"starts_at": "1919851200", "ends_at": "1919858400"}),
    ],
)
def test_invalid_sqlite_integer_or_numeric_datetime_is_422(
    client, auth_headers, game_data, path, changes
):
    if path == "/matching/requests":
        response = client.post(
            path,
            headers=auth_headers(game_data["player"]),
            json=matching_payload(game_data["venue"]) | changes,
        )
    else:
        response = client.get(path, params=changes)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("blocked_by", [None, "rank", "budget", "policy", "closed"])
def test_doubles_matching_checks_all_four_members(
    client, auth_headers, game_data, db_session_factory, blocked_by
):
    with db_session_factory() as db:
        extra = UserModel(
            email="fourth@example.com",
            password_hash="test-only",
            display_name="Fourth",
            skill_level=11 if blocked_by == "rank" else 10,
            gender="FEMALE",
            created_at=datetime(2030, 11, 1, tzinfo=timezone.utc),
            updated_at=datetime(2030, 11, 1, tzinfo=timezone.utc),
        )
        db.add(extra)
        db.flush()
        actors = [game_data["host"], game_data["player"], game_data["other"], extra.id]
        db.get(UserModel, actors[0]).skill_level = 8
        db.get(UserModel, actors[2]).skill_level = 10
        db.commit()
    payload = matching_payload(game_data["venue"]) | {"play_type": "DOUBLES"}
    for index, actor in enumerate(actors[:3]):
        candidate = payload | {"proposed_fee_male_vnd": 50000}
        if index == 0 and blocked_by == "budget":
            candidate["budget_max_vnd"] = 55000
        if index == 0 and blocked_by == "policy":
            candidate["gender_policy"] = "MALE_ONLY"
        response = client.post("/matching/requests", json=candidate, headers=auth_headers(actor))
        assert response.status_code == 201, response.text
        assert response.json()["suggestion"] is None
    if blocked_by == "closed":
        with db_session_factory() as db:
            request = db.scalar(
                select(MatchingRequestModel).where(MatchingRequestModel.user_id == actors[0])
            )
            request.status, request.closed_reason, request.closed_at = (
                "CLOSED",
                "REPLACED",
                request.created_at,
            )
            db.commit()
    # Caller nữ chỉ cần đủ phí nữ; phí nam cao hơn budget của caller vẫn hợp lệ.
    result = client.post(
        "/matching/requests",
        json=payload | {"budget_max_vnd": 40000},
        headers=auth_headers(actors[3]),
    )
    assert result.status_code == 201, result.text
    suggestion = result.json()["suggestion"]
    if blocked_by is None:
        assert suggestion["capacity"] == 4
        assert {member["id"] for member in suggestion["members"]} == set(actors)
    else:
        assert suggestion is None
