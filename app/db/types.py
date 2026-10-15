"""Database value converters shared by all repositories."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.domain.time_rules import ensure_utc_aware

_DB_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_db_utc(value: datetime) -> str:
    """Serialize an aware datetime using the single SQLite UTC text format."""
    return ensure_utc_aware(value).strftime(_DB_UTC_FORMAT)


def from_db_utc(value: str) -> datetime:
    """Deserialize the canonical SQLite UTC text format."""
    parsed = datetime.strptime(value, _DB_UTC_FORMAT)
    return parsed.replace(tzinfo=timezone.utc)


class UTCDateTimeText(TypeDecorator[datetime]):
    """Persist aware datetimes as fixed-format UTC TEXT in SQLite."""

    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        return to_db_utc(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        return from_db_utc(value)
