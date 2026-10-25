from typing import Generic, TypeVar, Literal, Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.domain.enums import Gender, GenderPolicy, PlayType, Status
from app.domain.time_rules import to_utc

T = TypeVar("T")

UtcDatetime = Annotated[AwareDatetime, AfterValidator(to_utc)]

class VenueQuery(BaseModel):

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=100)
    district_code: str | None = Field(default=None, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class VenueView(BaseModel):
    id: int
    name: str
    address: str
    district_code: str

class SessionQuery(BaseModel):

    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    district_code: str | None = None
    venue_id: int | None = None
    play_type: PlayType | None = None

    starts_at: UtcDatetime | None = None
    ends_at: UtcDatetime | None = None

    min_level: int | None = None
    max_level: int | None = None

    gender_policy: GenderPolicy | None = None

    fee_min: int | None = Field(default=None, ge=0)
    fee_max: int | None = Field(default=None, ge=0)

    only_available: bool = True
    host_me: bool = False                       # thiếu JWT -> 401 (xử lý ở api.py)

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class SessionView(BaseModel):
    id: int

    host_user_id: int
    venue_id: int

    title: str
    notes: str

    starts_at: UtcDatetime
    ends_at: UtcDatetime

    play_type: str
    fee_male_vnd: int
    fee_female_vnd: int

    min_level:str
    max_level: str
    gender_policy: str

    status: str
    created_at: UtcDatetime
    cancelled_at: UtcDatetime

class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

class CreateMatchingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_id: int | None = Field(default=None, ge=0)
    play_type: PlayType | None = None

    starts_at: UtcDatetime | None = None
    ends_at: UtcDatetime | None = None

    proposed_fee_male_vnd: int | None = Field(default=None, gt=0)
    proposed_fee_female_vnd: int | None = Field(default=None, gt=0)
    budget_max_vnd: int | None = Field(default=None, gt=0)
    gender_policy: GenderPolicy | None = None

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
    id: int
    venue_id: int

    starts_at: UtcDatetime
    ends_at: UtcDatetime

    play_type: PlayType
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    budget_max_vnd: int

    gender_policy: GenderPolicy
    status: Status
    closed_reason: str | None

    created_at: UtcDatetime
    closed_at: UtcDatetime | None


class SuggestedMember(BaseModel):
    id: int
    display_name: str
    skill_level: int
    gender: Gender
    estimated_fee_vnd: int


class MatchingSuggestion(BaseModel):
    venue_id: int
    play_type: PlayType
    capacity: Literal[2, 4]
    starts_at: UtcDatetime
    ends_at: UtcDatetime
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    members: list[SuggestedMember]
    requires_confirmation: Literal[True]


class MatchingResult(BaseModel):

    request: MatchingRequestSelf
    suggestion: MatchingSuggestion | None





