from typing import Annotated, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.api.schemas import PlayerSummary as PlayerSummary
from app.api.schemas import UtcDatetime
from app.domain.enums import (
    DisplayStatus,
    Gender,
    GenderPolicy,
    PlayType,
    SessionStatus,
    SkillLevel,
)

T = TypeVar("T")

IdInt = Annotated[int, Field(strict=True, gt=0, le=9223372036854775807)]
VndInt = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]


class VenueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_code: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=9223372036854775807)


class VenueView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    district_code: str
    is_active: bool


class SessionQuery(VenueQuery):
    model_config = ConfigDict(extra="forbid")

    venue_id: int | None = Field(None, gt=0, le=9223372036854775807)
    play_type: PlayType | None = None

    available_from: UtcDatetime | None = None
    available_to: UtcDatetime | None = None

    skill_level: SkillLevel | None = None
    gender: Gender | None = None
    max_fee_vnd: int | None = Field(None, ge=0, le=9223372036854775807)

    only_available: bool = True
    host_me: bool = False  # thiếu JWT -> 401

    @model_validator(mode="after")
    def _check_window(self):
        if (self.available_from is None) != (self.available_to is None):
            raise ValueError("available_from và available_to phải cùng có hoặc cùng không có")
        if self.available_from is not None and not self.available_from < self.available_to:
            raise ValueError("available_from phải nhỏ hơn available_to")
        return self


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    host: PlayerSummary
    venue: VenueView

    starts_at: UtcDatetime
    ends_at: UtcDatetime

    play_type: PlayType
    capacity: int

    fee_male_vnd: int
    fee_female_vnd: int

    min_level: SkillLevel
    max_level: SkillLevel

    gender_policy: GenderPolicy
    status: SessionStatus
    display_status: DisplayStatus

    accepted_count: int
    remaining_capacity: int


class PageResult(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    limit: int
    offset: int
