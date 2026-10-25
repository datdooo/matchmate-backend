
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.features.discovery.schemas import (
    CreateMatchingRequest,
    MatchingRequestSelf,
    MatchingResult,
    MatchingSuggestion,
    PageResult,
    SessionQuery,
    SessionView,
    SuggestedMember,
    VenueQuery,
    VenueView,
)

START = "2026-11-01T19:00:00+07:00"
END = "2026-11-01T21:00:00+07:00"


def matching_request(**overrides):
    data = {
        "venue_id": 1,
        "play_type": "DOUBLES",
        "starts_at": START,
        "ends_at": END,
        "proposed_fee_male_vnd": 80000,
        "proposed_fee_female_vnd": 70000,
        "budget_max_vnd": 90000,
        "gender_policy": "ANY",
    }
    return data | overrides


def venue(**overrides):
    data = {
        "id": 1,
        "name": "Demo Venue",
        "address": "Dong Da, Ha Noi",
        "district_code": "DONG_DA",
    }
    return data | overrides


def session(**overrides):
    data = {
        "id": 1,
        "host_user_id": 10,
        "venue_id": 1,
        "title": "Keo demo",
        "notes": "",
        "starts_at": START,
        "ends_at": END,
        "play_type": "DOUBLES",
        "fee_male_vnd": 80000,
        "fee_female_vnd": 70000,
        "min_level": "BEGINNER",
        "max_level": "INTERMEDIATE",
        "gender_policy": "ANY",
        "status": "OPEN",
        "created_at": START,
        "cancelled_at": END,
    }
    return data | overrides


def member(i=1, **overrides):
    data = {
        "id": i,
        "display_name": f"Player {i}",
        "skill_level": 2,
        "gender": "MALE",
        "estimated_fee_vnd": 80000,
    }
    return data | overrides


def request_self(**overrides):
    data = {
        "id": 1,
        "venue_id": 1,
        "starts_at": START,
        "ends_at": END,
        "play_type": "SINGLES",
        "proposed_fee_male_vnd": 80000,
        "proposed_fee_female_vnd": 70000,
        "budget_max_vnd": 90000,
        "gender_policy": "ANY",
        "status": "ACTIVE",
        "closed_reason": None,
        "created_at": START,
        "closed_at": None,
    }
    return data | overrides


def suggestion(**overrides):
    data = {
        "venue_id": 1,
        "play_type": "SINGLES",
        "capacity": 2,
        "starts_at": START,
        "ends_at": END,
        "proposed_fee_male_vnd": 80000,
        "proposed_fee_female_vnd": 70000,
        "members": [member(1), member(2)],
        "requires_confirmation": True,
    }
    return data | overrides


# Venue and session queries

def test_venue_query_pagination_and_extra_fields():
    assert VenueQuery().limit == 20
    assert VenueQuery(limit=50, offset=10).offset == 10

    with pytest.raises(ValidationError):
        VenueQuery(limit=101)

    with pytest.raises(ValidationError):
        VenueQuery(offset=-1)

    with pytest.raises(ValidationError):
        VenueQuery(foo=1)


def test_session_query_defaults_and_validation():
    query = SessionQuery()

    assert query.only_available is True
    assert query.host_me is False
    assert query.limit == 20

    with pytest.raises(ValidationError):
        SessionQuery(limit=0)

    with pytest.raises(ValidationError):
        SessionQuery(play_type="TRIPLES")


# Matching request

def test_create_matching_request_valid_and_utc():
    result = CreateMatchingRequest(**matching_request())

    assert result.starts_at.utcoffset() == timedelta(0)
    assert result.ends_at.utcoffset() == timedelta(0)


def test_create_matching_request_rejects_invalid_input():
    with pytest.raises(ValidationError):
        CreateMatchingRequest(**matching_request(foo=1))

    with pytest.raises(ValidationError):
        CreateMatchingRequest(
            **matching_request(proposed_fee_male_vnd=0)
        )

    with pytest.raises(ValidationError):
        CreateMatchingRequest(**matching_request(play_type="TRIPLES"))


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [
        ("2026-11-01T19:00:00", END),
        (START, "2026-11-01T21:00:00"),
        (END, START),
        (START, "2026-11-01T19:30:00+07:00"),
        (START, "2026-11-02T00:00:00+07:00"),
    ],
)
def test_create_matching_request_rejects_invalid_time_window(
    starts_at, ends_at
):
    with pytest.raises(ValidationError):
        CreateMatchingRequest(
            **matching_request(
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )


# Response schemas

def test_venue_view_and_session_view():
    v = VenueView(**venue())
    assert v.id == 1
    assert v.district_code == "DONG_DA"

    s = SessionView(**session())
    assert s.id == 1
    assert s.starts_at.utcoffset() == timedelta(0)
    assert s.created_at.utcoffset() == timedelta(0)


def test_session_view_rejects_missing_required_field():
    data = session()
    del data["host_user_id"]

    with pytest.raises(ValidationError):
        SessionView(**data)


def test_page_result():
    page = PageResult[VenueView](
        items=[venue()],
        total=1,
        limit=20,
        offset=0,
    )

    assert page.total == 1
    assert page.items[0].id == 1


# Matching responses

def test_matching_request_self_nullable_fields():
    result = MatchingRequestSelf(**request_self())

    assert result.closed_reason is None
    assert result.closed_at is None


def test_suggested_member():
    result = SuggestedMember(**member())

    assert result.id == 1
    assert result.estimated_fee_vnd == 80000


def test_matching_suggestion_requires_confirmation():
    result = MatchingSuggestion(**suggestion())

    assert len(result.members) == 2
    assert result.requires_confirmation is True

    with pytest.raises(ValidationError):
        MatchingSuggestion(
            **suggestion(requires_confirmation=False)
        )

    with pytest.raises(ValidationError):
        MatchingSuggestion(**suggestion(capacity=3))


def test_matching_result_allows_null_suggestion():
    result = MatchingResult(
        request=request_self(),
        suggestion=None,
    )

    assert result.suggestion is None
