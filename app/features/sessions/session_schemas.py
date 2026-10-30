from datetime import datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.domain.enums import Gender, SkillLevel
from app.domain.time_rules import to_utc
from app.features.sessions.session_contracts import CreateSessionInput


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_id: int = Field(strict=True, gt=0)
    title: str = Field(strict=True, min_length=1, max_length=120)
    notes: str = Field(default="", strict=True, max_length=1000)

    starts_at: AwareDatetime
    ends_at: AwareDatetime
    play_type: Literal["SINGLES", "DOUBLES"]

    fee_male_vnd: int = Field(strict=True, ge=0)
    fee_female_vnd: int = Field(strict=True, ge=0)

    min_level: SkillLevel
    max_level: SkillLevel
    gender_policy: Literal["ANY", "MALE_ONLY", "FEMALE_ONLY"] = "ANY"

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def reject_numeric_time(cls, value: object) -> object:
        if not isinstance(value, (str, datetime)):
            raise ValueError("Thời gian phải là datetime có múi giờ")
        return value

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return to_utc(value)

    def to_input(self) -> CreateSessionInput:
        return CreateSessionInput(**self.model_dump())


class PlayerSummary(BaseModel):
    id: int
    display_name: str
    skill_level: SkillLevel
    gender: Gender


class VenueView(BaseModel):
    id: int
    name: str
    address: str
    district_code: str
    distance_km: float | None


class ParticipationRecord(BaseModel):
    id: int
    user_id: int
    session_id: int
    player: PlayerSummary
    status: Literal["PENDING", "ACCEPTED", "REJECTED", "CANCELLED"]
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: Literal["MALE", "FEMALE"]
    quoted_fee_vnd: int


class Management(BaseModel):
    participations: list[ParticipationRecord]


class SessionDetail(BaseModel):
    id: int
    title: str
    notes: str
    host: PlayerSummary
    venue: VenueView
    starts_at: datetime
    ends_at: datetime
    play_type: Literal["SINGLES", "DOUBLES"]
    capacity: Literal[2, 4]
    fee_male_vnd: int
    fee_female_vnd: int
    min_level: SkillLevel
    max_level: SkillLevel
    gender_policy: Literal["ANY", "MALE_ONLY", "FEMALE_ONLY"]
    status: Literal["OPEN", "CANCELLED"]
    display_status: Literal["CANCELLED", "ENDED", "STARTED", "FULL", "AVAILABLE"]
    accepted_count: int
    remaining_capacity: int
    created_at: datetime
    cancelled_at: datetime | None
    my_participations: list[ParticipationRecord]
    management: Management | None
