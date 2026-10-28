from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.enums import (
    CloseReason,
    DisplayStatus,
    EffectiveStatus,
    Gender,
    GenderPolicy,
    MatchingStatus,
    PlayType,
    SessionStatus,
    SkillLevel,
)
from app.domain.time_rules import to_utc

T = TypeVar("T")

UtcDatetime = Annotated[AwareDatetime, AfterValidator(to_utc)]

IdInt = Annotated[int, Field(strict=True, gt=0)]
VndInt = Annotated[int, Field(strict=True, ge=0)]


class VenueQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_code: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class VenueView(BaseModel):
    id: int
    name: str
    address: str
    district_code: str
    is_active: bool


class SessionQuery(VenueQuery):
    model_config = ConfigDict(extra="forbid")

    venue_id: int | None = Field(None, gt=0)
    play_type: PlayType | None = None

    available_from: UtcDatetime | None = None
    available_to: UtcDatetime | None = None

    skill_level: SkillLevel | None = None
    gender: Gender | None = None
    max_fee_vnd: int | None = Field(None, ge=0)

    fee_min: int | None = Field(default=None, ge=0)
    fee_max: int | None = Field(default=None, ge=0)

    only_available: bool = True
    host_me: bool = False  # thiếu JWT -> 401 (xử lý ở api.py)

    @model_validator(mode="after")
    def _check_window(self):
        if (self.available_from is None) != (self.available_to is None):
            raise ValueError("available_from và available_to phải cùng có hoặc cùng không có")
        if self.available_from is not None and not self.available_from < self.available_to:
            raise ValueError("available_from phải nhỏ hơn available_to")
        return self


class PlayerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    skill_level: SkillLevel
    gender: Gender


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


class CreateMatchingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_id: IdInt

    starts_at: UtcDatetime
    ends_at: UtcDatetime

    play_type: PlayType
    proposed_fee_male_vnd: VndInt
    proposed_fee_female_vnd: VndInt
    budget_max_vnd: VndInt

    gender_policy: GenderPolicy = GenderPolicy.ANY

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.starts_at is None or self.ends_at is None:
            raise ValueError("starts_at và ends_at là bắt buộc")

        duration = (self.ends_at - self.starts_at).total_seconds() / 60

        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at phải bé hơn ends_at")

        if not 60 <= duration <= 240:
            raise ValueError("Thời gian trong khoảng 60-240 phút")

        return self


class MatchingRequestSelf(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int

    starts_at: UtcDatetime
    ends_at: UtcDatetime

    play_type: PlayType
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    budget_max_vnd: int

    gender_policy: GenderPolicy
    status: MatchingStatus
    closed_reason: CloseReason | None
    effective_status: EffectiveStatus

    created_at: UtcDatetime
    closed_at: UtcDatetime | None


class SuggestedMember(PlayerSummary):
    estimated_fee_vnd: int


class MatchingSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    venue_id: int
    play_type: PlayType
    capacity: Literal[2, 4]
    starts_at: UtcDatetime
    ends_at: UtcDatetime
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    members: list[SuggestedMember]
    requires_confirmation: Literal[True]

    @model_validator(mode="after")
    def _check_members(self):
        if len(self.members) != self.capacity:
            raise ValueError("số members phải bằng capacity")
        return self


class MatchingResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request: MatchingRequestSelf
    suggestion: MatchingSuggestion | None
