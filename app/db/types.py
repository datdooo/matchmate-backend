from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.types import TypeDecorator

from app.domain.time_rules import to_utc

DB_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_db_utc(value: datetime) -> str:
    return to_utc(value).strftime(DB_UTC_FORMAT)


def from_db_utc(value: str) -> datetime:
    return datetime.strptime(value, DB_UTC_FORMAT).replace(tzinfo=timezone.utc)


class UTCDateTimeText(TypeDecorator[datetime]):
    """Datetime UTC trong Python, TEXT trên SQLite và TIMESTAMPTZ trên PostgreSQL."""

    impl = String(27)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(DateTime(timezone=True))
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | str | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return to_utc(value)
        return to_db_utc(value)

    def process_result_value(self, value: datetime | str | None, dialect) -> datetime | None:
        if value is None:
            return None
        return to_utc(value) if isinstance(value, datetime) else from_db_utc(value)
