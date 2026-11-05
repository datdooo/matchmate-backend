from datetime import datetime, timedelta, timezone

import pytest

from app.domain.time_rules import is_valid_time_window, overlaps, to_utc


def test_normalizes_offset_to_utc() -> None:
    local = datetime.fromisoformat("2026-11-01T19:00:00+07:00")

    assert to_utc(local) == datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def test_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        to_utc(datetime(2026, 11, 1, 19))


@pytest.mark.parametrize(
    ("start_minutes", "end_minutes", "expected"),
    [
        (30, 90, True),  # Chồng một phần.
        (0, 120, True),  # Trùng toàn bộ.
        (30, 60, True),  # Nằm trong lịch đầu.
        (120, 180, False),  # Bắt đầu đúng lúc lịch đầu kết thúc.
        (-60, 0, False),  # Kết thúc đúng lúc lịch đầu bắt đầu.
    ],
)
def test_overlap_boundaries(
    start_minutes: int,
    end_minutes: int,
    expected: bool,
) -> None:
    start = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    other_start = start + timedelta(minutes=start_minutes)
    other_end = start + timedelta(minutes=end_minutes)

    assert overlaps(start, end, other_start, other_end) is expected
    # Đổi thứ tự hai lịch phải cho cùng kết quả.
    assert overlaps(other_start, other_end, start, end) is expected


@pytest.mark.parametrize("duration_minutes", [59, 60, 240, 241])
def test_time_window_duration(duration_minutes: int) -> None:
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    start = now + timedelta(hours=1)
    end = start + timedelta(minutes=duration_minutes)

    assert is_valid_time_window(start, end, now) is (60 <= duration_minutes <= 240)


@pytest.mark.parametrize("start_offset", [-1, 0, 1])
def test_time_window_must_start_in_future(start_offset: int) -> None:
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    start = now + timedelta(seconds=start_offset)
    end = start + timedelta(hours=2)

    assert is_valid_time_window(start, end, now) is (start_offset > 0)
