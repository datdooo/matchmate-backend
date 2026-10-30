from datetime import datetime, timedelta, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def to_utc(value: datetime) -> datetime:
    """Chuẩn hóa datetime có múi giờ về UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")

    return value.astimezone(timezone.utc)


def overlaps(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    """Kiểm hai lịch có chồng giờ; lịch nối tiếp được phép."""
    first_start = to_utc(first_start)
    first_end = to_utc(first_end)
    second_start = to_utc(second_start)
    second_end = to_utc(second_end)

    if first_start >= first_end or second_start >= second_end:
        raise ValueError("start must be before end")

    # Khoảng [start, end) không bao gồm thời điểm kết thúc.
    return first_start < second_end and second_start < first_end


def is_valid_time_window(
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
) -> bool:
    """Lịch mới phải ở tương lai và dài từ 60 đến 240 phút."""
    starts_at = to_utc(starts_at)
    ends_at = to_utc(ends_at)
    now = to_utc(now)

    duration = ends_at - starts_at
    return starts_at > now and timedelta(minutes=60) <= duration <= timedelta(minutes=240)
