from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import composition
from app.db.models import MatchingRequestModel, UserModel, VenueModel

NOW = datetime(2030, 11, 2, 10, tzinfo=timezone.utc)
STARTS_AT = NOW + timedelta(hours=2)
ENDS_AT = STARTS_AT + timedelta(hours=2)
VENUE_ID = 10
CALLER_ID = 100
PREVIOUS_REQUEST_ID = 900
NEW_REQUEST_ID = 901


@dataclass(frozen=True)
class Candidate:
    request_id: int
    user_id: int
    minute: int = 1
    rank: int = 9
    gender: str = "MALE"
    policy: str = "ANY"
    budget: int = 60_000


@pytest.mark.parametrize(
    ("play_type", "candidates", "expected_members"),
    [
        pytest.param("SINGLES", (), None, id="no-candidates"),
        pytest.param(
            "SINGLES",
            (Candidate(200, 201, gender="UNSPECIFIED"),),
            None,
            id="too-few-singles-after-filter",
        ),
        pytest.param(
            "DOUBLES",
            (Candidate(200, 201), Candidate(210, 211)),
            None,
            id="too-few-doubles",
        ),
        pytest.param(
            "SINGLES",
            (Candidate(200, 201, rank=12),),
            None,
            id="rank-spread",
        ),
        pytest.param(
            "SINGLES",
            (Candidate(200, 201, gender="FEMALE", policy="FEMALE_ONLY"),),
            None,
            id="gender-policy",
        ),
        pytest.param(
            "SINGLES",
            (Candidate(200, 201, budget=59_999),),
            None,
            id="budget",
        ),
        pytest.param(
            "DOUBLES",
            (
                Candidate(200, 201, minute=1),
                Candidate(210, 211, minute=2, rank=11),
                Candidate(220, 221, minute=3, gender="FEMALE", budget=40_000),
                Candidate(230, 231, minute=4, rank=10),
                Candidate(240, 241, minute=5, rank=12),
            ),
            [100, 231, 221, 211],
            id="first-valid-of-several-doubles",
        ),
        pytest.param(
            "SINGLES",
            (Candidate(210, 201), Candidate(200, 211)),
            [100, 211],
            id="same-created-at-order-by-request-id",
        ),
    ],
)
def test_phase1_matching_corpus(
    client, auth_headers, db_session_factory, monkeypatch, play_type, candidates, expected_members
):
    clock = SimpleNamespace(now=lambda: NOW)
    monkeypatch.setattr(composition, "SystemClock", lambda: clock)
    payload = {
        "venue_id": VENUE_ID,
        "starts_at": STARTS_AT,
        "ends_at": ENDS_AT,
        "play_type": play_type,
        "gender_policy": "ANY",
        "proposed_fee_male_vnd": 60_000,
        "proposed_fee_female_vnd": 40_000,
        "budget_max_vnd": 60_000,
    }
    prior = Candidate(PREVIOUS_REQUEST_ID, CALLER_ID, minute=6)
    with db_session_factory.begin() as db:
        db.add(VenueModel(id=VENUE_ID, name="Sân mẫu", address="Test", district_code="CAU_GIAY"))
        for entrant in (*candidates, prior):
            db.add(
                UserModel(
                    id=entrant.user_id,
                    email=f"player-{entrant.user_id}@example.invalid",
                    password_hash="fixture-only",
                    display_name=f"Player {entrant.user_id}",
                    skill_level=entrant.rank,
                    gender=entrant.gender,
                    created_at=NOW - timedelta(days=1),
                    updated_at=NOW - timedelta(days=1),
                )
            )
        db.flush()
        for entrant in (*candidates, prior):
            db.add(
                MatchingRequestModel(
                    **(
                        payload
                        | {"budget_max_vnd": entrant.budget, "gender_policy": entrant.policy}
                    ),
                    id=entrant.request_id,
                    user_id=entrant.user_id,
                    status="ACTIVE",
                    created_at=NOW - timedelta(minutes=entrant.minute),
                )
            )

    response = client.post(
        "/matching/requests",
        headers=auth_headers(CALLER_ID),
        json=payload | {"starts_at": STARTS_AT.isoformat(), "ends_at": ENDS_AT.isoformat()},
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["request"]["id"] == NEW_REQUEST_ID
    suggestion = result["suggestion"]
    if expected_members is None:
        assert suggestion is None
    else:
        assert [member["id"] for member in suggestion["members"]] == expected_members
        assert suggestion["capacity"] == len(expected_members)
        assert suggestion["requires_confirmation"] is True
        for member in suggestion["members"]:
            assert "email" not in member and "budget_max_vnd" not in member
            assert (
                member["estimated_fee_vnd"] == {"MALE": 60_000, "FEMALE": 40_000}[member["gender"]]
            )

    with db_session_factory() as db:
        requests = db.scalars(
            select(MatchingRequestModel)
            .where(MatchingRequestModel.user_id == CALLER_ID)
            .order_by(MatchingRequestModel.id)
        ).all()
        assert [(row.id, row.status, row.closed_reason) for row in requests] == [
            (PREVIOUS_REQUEST_ID, "CLOSED", "REPLACED"),
            (NEW_REQUEST_ID, "ACTIVE", None),
        ]
