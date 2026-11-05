from datetime import datetime, timezone

import pytest

from app.db.types import from_db_utc, to_db_utc


def test_to_db_utc_normalizes_offset_datetime():
    value = datetime.fromisoformat("2026-11-01T19:00:00+07:00")

    assert to_db_utc(value) == "2026-11-01T12:00:00.000000Z"


def test_from_db_utc_returns_aware_utc_datetime():
    value = from_db_utc("2026-11-01T12:00:00.000000Z")

    assert value == datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    assert value.tzinfo == timezone.utc


def test_to_db_utc_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        to_db_utc(datetime(2026, 11, 1, 12, 0))
