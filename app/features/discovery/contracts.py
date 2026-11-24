from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Protocol, TypeVar

from app.domain.entities import PlayerSummary as PlayerSummary
from app.domain.enums import (
    DisplayStatus,
    Gender,
    GenderPolicy,
    PlayType,
    SessionStatus,
)
from app.features.catalog.contracts import VenueSummary as VenueRecord

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# Venue


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


class DiscoveryRepository(Protocol):
    def find_venues(self, filter: VenueFilter) -> Page[VenueRecord]:
        """Trả về sân theo yêu cầu."""

    def find_sessions(self, filter: SessionFilter) -> Page[SessionRecord]:
        """Trả về session theo yêu cầu."""
