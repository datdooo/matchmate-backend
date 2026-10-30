from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, AwareDatetime, BaseModel, BeforeValidator

from app.domain.time_rules import to_utc


def parse_iso_datetime(value):
    """Không nhận Unix timestamp; JSON phải gửi datetime ISO 8601 có timezone."""
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        raise ValueError("Thời gian phải là ISO 8601 có múi giờ")
    return value


UtcDatetime = Annotated[AwareDatetime, BeforeValidator(parse_iso_datetime), AfterValidator(to_utc)]


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorPayload
