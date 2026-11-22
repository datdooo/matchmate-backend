"""Pure data contracts owned by Matching; skill levels use ranks from 1 to 19."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities import PlayerSummary as PlayerSummary
from app.domain.enums import CloseReason, Gender, GenderPolicy, MatchingStatus, PlayType


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


@dataclass(frozen=True)
class CreateMatchingInput:
    venue_id: int
    starts_at: datetime
    ends_at: datetime
    play_type: PlayType
    proposed_fee_male_vnd: int
    proposed_fee_female_vnd: int
    budget_max_vnd: int
    gender_policy: GenderPolicy = GenderPolicy.ANY


@dataclass(frozen=True)
class MatchingFilter:
    venue_id: int
    play_type: PlayType
    starts_at: datetime
    ends_at: datetime
    exclude_user_id: int
    now: datetime


@dataclass(frozen=True)
class MatchingResult:
    request: MatchingRequestRecord
    suggestion: MatchingSuggestion | None


class MatchingRepository(Protocol):
    def close_active_for_user(self, user_id: int, reason: CloseReason, closed_at: datetime) -> None:
        """Đóng nhu cầu ACTIVE của user."""

    def create(
        self, data: CreateMatchingInput, user_id: int, created_at: datetime
    ) -> MatchingRequestRecord:
        """Tạo nhu cầu ACTIVE mới và trả bản ghi đã tạo."""

    def candidates(self, matching_filter: MatchingFilter) -> list[MatchingRequestRecord]:
        """Danh sách ứng viên theo MatchingFilter."""

    def has_accepted_overlap(self, user_id: int, starts_at: datetime, ends_at: datetime) -> bool:
        """Chồng giờ khi a < d và c < b."""


class MatchingStrategy(Protocol):
    def __call__(
        self,
        caller: PlayerSummary,
        caller_request: MatchingRequestRecord,
        candidates: list[MatchingCandidate],
    ) -> MatchingSuggestion | None: ...
