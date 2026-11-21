"""Pure data contracts owned by Matching; skill levels use ranks from 1 to 19."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import CloseReason, Gender, GenderPolicy, MatchingStatus, PlayType


@dataclass(frozen=True)
class PlayerSummary:
    id: int
    display_name: str
    skill_level: int
    gender: Gender


@dataclass(frozen=True)
class MatchingRequestRecord:
    id: int
    user_id: int
    venue_id: int

    starts_at: datetime
    ends_at: datetime

    play_type: PlayType
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    budget_max_vnd: int

    gender_policy: GenderPolicy

    status: MatchingStatus
    closed_reason: CloseReason | None
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class MatchingCandidate:
    request: MatchingRequestRecord
    player: PlayerSummary


@dataclass(frozen=True)
class SuggestedMember:
    id: int
    display_name: str
    skill_level: int
    gender: Gender
    estimated_fee_vnd: int


@dataclass(frozen=True)
class MatchingSuggestion:
    venue_id: int
    play_type: PlayType
    capacity: int
    starts_at: datetime
    ends_at: datetime
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    members: list[SuggestedMember]
    requires_confirmation: bool = True
