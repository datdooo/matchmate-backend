from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Protocol, TypeVar

from app.domain.enums import (
    CloseReason,
    DisplayStatus,
    Gender,
    GenderPolicy,
    PlayType,
    SessionStatus,
)
from app.features.matching.contracts import (
    MatchingCandidate as MatchingCandidate,
)
from app.features.matching.contracts import (
    MatchingRequestRecord as MatchingRequestRecord,
)
from app.features.matching.contracts import (
    MatchingSuggestion as MatchingSuggestion,
)
from app.features.matching.contracts import (
    PlayerSummary as PlayerSummary,
)
from app.features.matching.contracts import (
    SuggestedMember as SuggestedMember,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# Venue
@dataclass(frozen=True)
class VenueRecord:
    id: int
    name: str
    address: str
    district_code: str
    is_active: bool


@dataclass(frozen=True)
class VenueFilter:
    district_code: str | None = None
    limit: int = 20
    offset: int = 0


# Session
@dataclass(frozen=True)
class SessionRecord:
    id: int
    host: PlayerSummary
    venue: VenueRecord

    title: str
    notes: str

    starts_at: datetime
    ends_at: datetime

    play_type: PlayType
    fee_male_vnd: int
    fee_female_vnd: int

    min_level: int
    max_level: int
    gender_policy: GenderPolicy
    status: SessionStatus

    capacity: int
    accepted_count: int
    remaining_capacity: int
    display_status: DisplayStatus


@dataclass(frozen=True)
class SessionFilter:
    now: datetime

    district_code: str | None = None
    venue_id: int | None = None
    play_type: PlayType | None = None

    available_from: datetime | None = None
    available_to: datetime | None = None

    skill_level: int | None = None
    gender: Gender | None = None

    max_fee_vnd: int | None = None

    only_available: bool = True
    host_me: bool = False
    host_user_id: int | None = None
    only_listable: bool = True

    limit: int = 20
    offset: int = 0


# Matching


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


class DiscoveryRepository(Protocol):
    def find_venues(self, filter: VenueFilter) -> Page[VenueRecord]:
        """Trả về sân theo yêu cầu."""

    def find_sessions(self, filter: SessionFilter) -> Page[SessionRecord]:
        """Trả về session theo yêu cầu."""


class MatchingRepository(Protocol):
    def close_active_for_user(self, user_id: int, reason: CloseReason, closed_at: datetime) -> None:
        """Đóng nhu cầu ACTIVE của user."""

    def create(
        self, data: CreateMatchingInput, user_id: int, created_at: datetime
    ) -> MatchingRequestRecord:
        """Tạo nhu cầu ACTIVE mới và trả bản ghi đã tạo."""

    def candidates(self, matching_filter: MatchingFilter) -> list[MatchingCandidate]:
        """Danh sách ứng viên theo MatchingFilter."""

    def get_venue(self, venue_id: int) -> VenueRecord | None: ...

    def get_user(self, user_id: int) -> PlayerSummary | None: ...

    def has_accepted_overlap(self, user_id: int, starts_at: datetime, ends_at: datetime) -> bool:
        """Chồng giờ khi a < d và c < b."""
