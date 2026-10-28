from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.enums import GenderPolicy, PlayType
from app.features.discovery.router import to_matching_input
from app.features.discovery.schemas import CreateMatchingRequest


def _first(enum_cls):
    return next(iter(enum_cls))


def _valid_payload():
    starts_at = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    return {
        "venue_id": 1,
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(minutes=120),
        "play_type": _first(PlayType),
        "proposed_fee_male_vnd": 50000,
        "proposed_fee_female_vnd": 40000,
        "budget_max_vnd": 60000,
        "gender_policy": GenderPolicy.ANY,
    }


def test_create_matching_request_accepts_valid_payload():
    request = CreateMatchingRequest(**_valid_payload())

    assert request.venue_id == 1
    assert request.ends_at - request.starts_at == timedelta(minutes=120)


@pytest.mark.parametrize("duration_minutes", [59, 241])
def test_create_matching_request_rejects_duration_outside_range(duration_minutes):
    payload = _valid_payload()
    payload["ends_at"] = payload["starts_at"] + timedelta(minutes=duration_minutes)

    with pytest.raises(ValidationError):
        CreateMatchingRequest(**payload)


def test_create_matching_request_rejects_end_before_start():
    payload = _valid_payload()
    payload["ends_at"] = payload["starts_at"]

    with pytest.raises(ValidationError):
        CreateMatchingRequest(**payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("venue_id", 0),
        ("proposed_fee_male_vnd", -1),
        ("proposed_fee_female_vnd", -1),
        ("budget_max_vnd", -1),
    ],
)
def test_create_matching_request_rejects_invalid_positive_or_fee_values(field, value):
    payload = _valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        CreateMatchingRequest(**payload)


def test_to_matching_input_copies_request_fields():
    request = CreateMatchingRequest(**_valid_payload())

    result = to_matching_input(request)

    assert result.venue_id == request.venue_id
    assert result.starts_at == request.starts_at
    assert result.ends_at == request.ends_at
    assert result.play_type == request.play_type
    assert result.proposed_fee_male_vnd == request.proposed_fee_male_vnd
    assert result.proposed_fee_female_vnd == request.proposed_fee_female_vnd
    assert result.budget_max_vnd == request.budget_max_vnd
    assert result.gender_policy == request.gender_policy
