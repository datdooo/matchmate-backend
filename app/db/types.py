from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

DB_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def to_db_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")

    return value.astimezone(timezone.utc).strftime(DB_UTC_FORMAT)


def from_db_utc(value: str) -> datetime:
    return datetime.strptime(value, DB_UTC_FORMAT).replace(tzinfo=timezone.utc)


class UTCDateTimeText(TypeDecorator[datetime]):
    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> str | None:
        if value is None:
            return None
        return to_db_utc(value)

    def process_result_value(self, value: str | None, dialect) -> datetime | None:
        if value is None:
            return None
        return from_db_utc(value)
