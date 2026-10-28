from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.enums import Gender, PlayType, SkillLevel, skill_to_rank
from app.features.discovery.contracts import SessionFilter
from app.features.discovery.router import to_session_filter
from app.features.discovery.schemas import SessionQuery


def _first(enum_cls):
    return next(iter(enum_cls))


def test_session_query_defaults():
    query = SessionQuery()

    assert query.limit == 20
    assert query.offset == 0
    assert query.only_available is True
    assert query.host_me is False


@pytest.mark.parametrize(
    "payload",
    [
        {"venue_id": 0},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"max_fee_vnd": -1},
        {"available_from": "2026-11-01T10:00:00Z"},
        {"available_to": "2026-11-01T12:00:00Z"},
        {"unknown_filter": True},
    ],
)
def test_session_query_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        SessionQuery(**payload)


def test_session_query_rejects_reversed_or_equal_time_window():
    start = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)

    with pytest.raises(ValidationError):
        SessionQuery(
            available_from=start,
            available_to=start,
        )

    with pytest.raises(ValidationError):
        SessionQuery(
            available_from=start + timedelta(hours=2),
            available_to=start,
        )


def test_session_query_accepts_complete_time_window():
    start = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    query = SessionQuery(
        available_from=start,
        available_to=start + timedelta(hours=2),
    )

    assert query.available_from is not None
    assert query.available_to is not None
    assert query.available_from < query.available_to


def test_to_session_filter_maps_fields_and_host_id():
    skill = _first(SkillLevel)
    gender = _first(Gender)
    play_type = _first(PlayType)
    query = SessionQuery(
        district_code="Q1",
        venue_id=3,
        play_type=play_type,
        skill_level=skill,
        gender=gender,
        max_fee_vnd=50000,
        only_available=False,
        host_me=True,
        limit=10,
        offset=5,
    )

    result = to_session_filter(query, viewer_id=42)

    assert isinstance(result, SessionFilter)
    assert result.district_code == "Q1"
    assert result.venue_id == 3
    assert result.play_type == play_type
    assert result.skill_level == skill_to_rank(skill)
    assert result.gender == gender
    assert result.max_fee_vnd == 50000
    assert result.only_available is False
    assert result.host_me is True
    assert result.host_user_id == 42
    assert (result.limit, result.offset) == (10, 5)
    assert result.now.tzinfo is not None


def test_to_session_filter_does_not_set_host_id_when_host_me_is_false():
    query = SessionQuery(host_me=False)

    result = to_session_filter(query, viewer_id=42)

    assert result.host_user_id is None
    assert result.host_me is False


def test_to_session_filter_allows_missing_viewer_id_when_host_me_is_false():
    query = SessionQuery(host_me=False)

    result = to_session_filter(query, viewer_id=None)

    assert result.host_user_id is None
