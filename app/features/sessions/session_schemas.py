from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.api.schemas import UtcDatetime
from app.domain.enums import SkillLevel
from app.features.discovery.schemas import PlayerSummary, SessionSummary
from app.features.sessions.session_contracts import CreateSessionInput


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_id: int = Field(strict=True, gt=0, le=9223372036854775807)
    title: str = Field(strict=True, min_length=1, max_length=120)
    notes: str = Field(default="", strict=True, max_length=1000)

    starts_at: UtcDatetime
    ends_at: UtcDatetime
    play_type: Literal["SINGLES", "DOUBLES"]

    fee_male_vnd: int = Field(strict=True, ge=0, le=9223372036854775807)
    fee_female_vnd: int = Field(strict=True, ge=0, le=9223372036854775807)

    min_level: SkillLevel
    max_level: SkillLevel
    gender_policy: Literal["ANY", "MALE_ONLY", "FEMALE_ONLY"] = "ANY"

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    def to_input(self) -> CreateSessionInput:
        return CreateSessionInput(**self.model_dump())


class ParticipationRecord(BaseModel):
    id: int
    user_id: int
    session_id: int
    player: PlayerSummary
    status: Literal["PENDING", "ACCEPTED", "REJECTED", "CANCELLED"]
    created_at: UtcDatetime
    decided_at: UtcDatetime | None
    cancelled_at: UtcDatetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: Literal["MALE", "FEMALE"]
    quoted_fee_vnd: int


class Management(BaseModel):
    participations: list[ParticipationRecord]


class SessionDetail(SessionSummary):
    # Detail mở rộng đúng summary chung, tránh list/detail lệch host, venue hoặc mã trình.
    notes: str
    created_at: UtcDatetime
    cancelled_at: UtcDatetime | None
    my_participations: list[ParticipationRecord]
    management: Management | None
