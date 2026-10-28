from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.features.discovery.schemas import (
    CreateMatchingRequest,
    MatchingRequestSelf,
    MatchingResult,
    MatchingSuggestion,
    SessionQuery,
    SessionSummary,
    VenueQuery,
)

START = "2026-11-01T19:00:00+07:00"
END = "2026-11-01T21:00:00+07:00"
PLAYER = {"id": 1, "display_name": "P1", "skill_level": "TB", "gender": "MALE"}
VENUE = {
    "id": 1, "name": "V", "address": "A", "district_code": "DONG_DA",  "is_active": True,
}  # fmt: skip
BODY = {
    "venue_id": 1, "play_type": "DOUBLES", "starts_at": START, "ends_at": END,
    "proposed_fee_male_vnd": 80000, "proposed_fee_female_vnd": 70000,
    "budget_max_vnd": 90000,
}  # fmt: skip
SESSION = {
    "id": 1, "title": "T", "host": PLAYER, "venue": VENUE, "starts_at": START,
    "ends_at": END, "play_type": "DOUBLES", "capacity": 4, "fee_male_vnd": 80000,
    "fee_female_vnd": 70000, "min_level": "TB_MINUS", "max_level": "TB_PLUS",
    "gender_policy": "ANY", "status": "OPEN", "display_status": "AVAILABLE",
    "accepted_count": 2, "remaining_capacity": 2,
}  # fmt: skip
REQUEST = {
    "id": 1, "venue_id": 1, "starts_at": START, "ends_at": END, "play_type": "SINGLES",
    "proposed_fee_male_vnd": 80000, "proposed_fee_female_vnd": 70000,
    "budget_max_vnd": 90000, "gender_policy": "ANY", "status": "ACTIVE",
    "effective_status": "ACTIVE", "closed_reason": None, "created_at": START,
    "closed_at": None,
}  # fmt: skip
MEMBER = PLAYER | {"estimated_fee_vnd": 80000}
SUGGESTION = {
    "venue_id": 1, "play_type": "SINGLES", "capacity": 2, "starts_at": START,
    "ends_at": END, "proposed_fee_male_vnd": 80000, "proposed_fee_female_vnd": 70000,
    "members": [MEMBER, MEMBER | {"id": 2}], "requires_confirmation": True,
}  # fmt: skip


def invalid(model, **data):
    with pytest.raises(ValidationError):
        model(**data)


def test_venue_query():
    assert (VenueQuery().limit, VenueQuery().offset) == (20, 0)
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        invalid(VenueQuery, **bad)


def test_session_query():
    q = SessionQuery()
    assert q.only_available is True and q.host_me is False and q.limit == 20
    for bad in ({"play_type": "X"}, {"max_fee_vnd": -1}, {"venue_id": 0}, {"foo": 1}):
        invalid(SessionQuery, **bad)


def test_session_query_window():
    ok = SessionQuery(available_from=START, available_to=END)
    assert ok.available_from.utcoffset() == timedelta(0)
    for bad in (
        {"available_from": START},  # thiếu một đầu
        {"available_from": END, "available_to": START},  # from > to
        {"available_from": START, "available_to": START},  # from == to
        {
            "available_from": "2026-11-01T19:00:00",
            "available_to": END,
        },  # thiếu timezone
    ):
        invalid(SessionQuery, **bad)


def test_create_matching_request_valid():
    r = CreateMatchingRequest(**BODY)
    assert r.starts_at.utcoffset() == timedelta(0)
    assert r.gender_policy.value == "ANY"
    assert CreateMatchingRequest(**BODY | {"budget_max_vnd": 0}).budget_max_vnd == 0


@pytest.mark.parametrize(
    "change",
    [
        {"user_id": 1},  # field thừa
        {"gender": "MALE"},
        {"venue_id": 0},
        {"budget_max_vnd": 90000.0},  # float
        {"budget_max_vnd": True},  # bool
        {"budget_max_vnd": "90000"},  # chuỗi
        {"proposed_fee_male_vnd": -1},
        {"starts_at": "2026-11-01T19:00:00"},  # thiếu timezone
    ],
)
def test_create_matching_request_invalid(change):
    invalid(CreateMatchingRequest, **BODY | change)


def test_create_matching_request_missing_field():
    invalid(CreateMatchingRequest, **{k: v for k, v in BODY.items() if k != "play_type"})


def test_session_summary():
    s = SessionSummary(**SESSION)
    assert s.host.display_name == "P1" and s.venue.name == "V"
    assert '"starts_at":"2026-11-01T12:00:00Z"' in s.model_dump_json()
    invalid(SessionSummary, **{k: v for k, v in SESSION.items() if k != "host"})
    invalid(SessionSummary, **SESSION | {"display_status": "OPEN"})


def test_matching_request_self_keeps_nullable_keys():
    r = MatchingRequestSelf(**REQUEST)
    assert r.closed_reason is None and r.closed_at is None
    invalid(
        MatchingRequestSelf,
        **{k: v for k, v in REQUEST.items() if k != "closed_reason"},
    )


def test_matching_suggestion():
    assert len(MatchingSuggestion(**SUGGESTION).members) == 2
    invalid(MatchingSuggestion, **SUGGESTION | {"capacity": 4})  # members != capacity
    invalid(MatchingSuggestion, **SUGGESTION | {"capacity": 3})
    invalid(MatchingSuggestion, **SUGGESTION | {"requires_confirmation": False})


def test_matching_result():
    r = MatchingResult(request=REQUEST, suggestion=None)
    assert r.model_dump(mode="json")["suggestion"] is None
    assert MatchingResult(request=REQUEST, suggestion=SUGGESTION).suggestion
    invalid(MatchingResult, request=REQUEST)  # thiếu key suggestion
