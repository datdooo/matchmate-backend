"""Clock abstraction and timezone guards used by pure business services."""

from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """Production clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def ensure_utc_aware(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone information")
    return value.astimezone(timezone.utc)
