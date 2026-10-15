"""Router contract tests independent of the shared composition root."""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.features.sessions.participation_api import router
from app.features.sessions.participation_contracts import (
    ParticipationDetail,
    PlayerSummary,
    SessionSummary,
    VenueView,
)
from app.features.sessions.participation_dependencies import get_participation_service
from tests.conftest import NOW


class FakeParticipationService:
    def _detail(self, *, status: str = "PENDING") -> ParticipationDetail:
        player = PlayerSummary(id=2, display_name="Player", skill_level="TB", gender="FEMALE")
        session = SessionSummary(
            id=1,
            title="Kèo demo",
            host=PlayerSummary(id=1, display_name="Host", skill_level="TB", gender="MALE"),
            venue=VenueView(
                id=1,
                name="Demo Venue",
                address="Demo",
                district_code="DONG_DA",
                latitude=21.0,
                longitude=105.8,
                distance_km=None,
            ),
            starts_at=NOW,
            ends_at=NOW,
            play_type="DOUBLES",
            capacity=4,
            fee_male_vnd=80000,
            fee_female_vnd=70000,
            min_level="TB_MINUS",
            max_level="TB_PLUS",
            gender_policy="ANY",
            status="OPEN",
            display_status="AVAILABLE",
            accepted_count=1,
            remaining_capacity=3,
        )
        return ParticipationDetail(
            id=10,
            user_id=2,
            session_id=1,
            player=player,
            status=status,
            created_at=NOW,
            decided_at=None,
            cancelled_at=None,
            can_cancel=True,
            can_decide=False,
            gender_at_join="FEMALE",
            quoted_fee_vnd=70000,
            session=session,
        )

    def join(self, actor_user_id: int, session_id: int) -> ParticipationDetail:
        assert actor_user_id == 2
        assert session_id == 1
        return self._detail()

    def decide(self, actor_user_id: int, participation_id: int, decision) -> ParticipationDetail:
        assert actor_user_id == 2
        assert participation_id == 10
        return replace(self._detail(), status="ACCEPTED", decided_at=NOW)

    def cancel(self, actor_user_id: int, participation_id: int) -> ParticipationDetail:
        assert actor_user_id == 2
        assert participation_id == 10
        return replace(self._detail(), status="CANCELLED", cancelled_at=NOW)


def _client() -> TestClient:
    app = FastAPI()
    fake = FakeParticipationService()
    app.dependency_overrides[get_participation_service] = lambda: fake

    @app.middleware("http")
    async def principal(request: Request, call_next):
        request.state.principal = {"user_id": 2}
        return await call_next(request)

    app.include_router(router)
    return TestClient(app)


def test_router_exposes_exact_three_participation_operations() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {
        "/participations",
        "/participations/{participation_id}/decision",
        "/participations/{participation_id}",
    }


def test_join_rejects_extra_fields_and_non_integer_session_id() -> None:
    with _client() as client:
        assert client.post("/participations", json={"session_id": 1}).status_code == 201
        assert (
            client.post(
                "/participations",
                json={"session_id": 1, "user_id": 99},
            ).status_code
            == 422
        )
        assert client.post("/participations", json={"session_id": "1"}).status_code == 422
        assert client.post("/participations", json={"session_id": True}).status_code == 422


def test_decision_and_delete_contract() -> None:
    with _client() as client:
        approved = client.post(
            "/participations/10/decision",
            json={"decision": "APPROVE"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "ACCEPTED"
        assert (
            client.post(
                "/participations/10/decision",
                json={"decision": "APPROVED"},
            ).status_code
            == 422
        )

        cancelled = client.delete("/participations/10")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
