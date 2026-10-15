"""Pure-Python contracts for the participation slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ContextManager, Protocol


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNSPECIFIED = "UNSPECIFIED"


class GenderPolicy(StrEnum):
    ANY = "ANY"
    MALE_ONLY = "MALE_ONLY"
    FEMALE_ONLY = "FEMALE_ONLY"


class PlayType(StrEnum):
    SINGLES = "SINGLES"
    DOUBLES = "DOUBLES"


class SessionStatus(StrEnum):
    OPEN = "OPEN"
    CANCELLED = "CANCELLED"


class DisplayStatus(StrEnum):
    CANCELLED = "CANCELLED"
    ENDED = "ENDED"
    STARTED = "STARTED"
    FULL = "FULL"
    AVAILABLE = "AVAILABLE"


class ParticipationStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


LEVEL_NAME_BY_RANK: dict[int, str] = {
    1: "NEWBIE",
    2: "Y_MINUS",
    3: "Y",
    4: "Y_PLUS",
    5: "TBY_MINUS",
    6: "TBY",
    7: "TBY_PLUS",
    8: "TB_MINUS",
    9: "TB",
    10: "TB_PLUS",
    11: "TBK_MINUS",
    12: "TBK",
    13: "TBK_PLUS",
    14: "K_MINUS",
    15: "K",
    16: "K_PLUS",
    17: "T_MINUS",
    18: "T",
    19: "T_PLUS",
}


@dataclass(frozen=True)
class UserProfile:
    id: int
    display_name: str
    skill_level: int
    gender: str


@dataclass(frozen=True)
class VenueRecord:
    id: int
    name: str
    address: str
    district_code: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class SessionRecord:
    id: int
    host_user_id: int
    venue_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    play_type: str
    fee_male_vnd: int
    fee_female_vnd: int
    min_level: int
    max_level: int
    gender_policy: str
    status: str
    host: UserProfile
    venue: VenueRecord

    @property
    def capacity(self) -> int:
        return 2 if self.play_type == PlayType.SINGLES else 4


@dataclass(frozen=True)
class Participation:
    id: int
    user_id: int
    session_id: int
    status: str
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
    gender_at_join: str
    quoted_fee_vnd: int


@dataclass(frozen=True)
class CreateParticipationInput:
    user_id: int
    session_id: int
    status: str
    gender_at_join: str
    quoted_fee_vnd: int
    decided_at: datetime | None = None


@dataclass(frozen=True)
class PlayerSummary:
    id: int
    display_name: str
    skill_level: str
    gender: str


@dataclass(frozen=True)
class VenueView:
    id: int
    name: str
    address: str
    district_code: str
    latitude: float
    longitude: float
    distance_km: float | None


@dataclass(frozen=True)
class SessionSummary:
    id: int
    title: str
    host: PlayerSummary
    venue: VenueView
    starts_at: datetime
    ends_at: datetime
    play_type: str
    capacity: int
    fee_male_vnd: int
    fee_female_vnd: int
    min_level: str
    max_level: str
    gender_policy: str
    status: str
    display_status: str
    accepted_count: int
    remaining_capacity: int


@dataclass(frozen=True)
class ParticipationRecord:
    id: int
    user_id: int
    session_id: int
    player: PlayerSummary
    status: str
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: str
    quoted_fee_vnd: int


@dataclass(frozen=True)
class ParticipationDetail:
    id: int
    user_id: int
    session_id: int
    player: PlayerSummary
    status: str
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
    can_cancel: bool
    can_decide: bool
    gender_at_join: str
    quoted_fee_vnd: int
    session: SessionSummary


class ParticipationError(Exception):
    """Domain error carrying the public MatchMate error contract."""

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class UserReader(Protocol):
    def get_by_id(self, user_id: int) -> UserProfile | None: ...


class SessionReader(Protocol):
    def get_by_id(self, session_id: int) -> SessionRecord | None: ...


class ParticipationRepository(Protocol):
    def get_by_id(self, participation_id: int) -> Participation | None: ...

    def count_accepted(self, session_id: int) -> int: ...

    def has_active(self, user_id: int, session_id: int) -> bool: ...

    def has_overlap(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        *,
        exclude_session_id: int | None = None,
    ) -> bool: ...

    def create(self, data: CreateParticipationInput, now: datetime) -> Participation: ...

    def set_status(
        self,
        participation_id: int,
        status: str,
        now: datetime,
    ) -> Participation: ...


class MatchingRequestWriter(Protocol):
    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None: ...


class ParticipationTransaction(Protocol):
    users: UserReader
    sessions: SessionReader
    participations: ParticipationRepository
    matching: MatchingRequestWriter

    def commit(self) -> None: ...


class ParticipationUnitOfWorkFactory(Protocol):
    def write(self) -> ContextManager[ParticipationTransaction]: ...
