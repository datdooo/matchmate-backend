from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas import PlayerSummary, UtcDatetime
from app.domain.enums import CloseReason, EffectiveStatus, GenderPolicy, MatchingStatus, PlayType

IdInt = Annotated[int, Field(strict=True, gt=0, le=9223372036854775807)]
VndInt = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]


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
