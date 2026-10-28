from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities import Participation, Session
from app.domain.enums import Gender, ParticipationStatus
from app.features.discovery.contracts import PlayerSummary, SessionRecord


@dataclass(frozen=True)
class CreateParticipationInput:
    user_id: int
    session_id: int
    gender_at_join: Gender
    quoted_fee_vnd: int
    status: ParticipationStatus = ParticipationStatus.PENDING


@dataclass(frozen=True)
class ParticipationRecord(Participation):
    player: PlayerSummary
    can_cancel: bool
    can_decide: bool


@dataclass(frozen=True)
class ParticipationDetail(ParticipationRecord):
    # Dùng DTO thuần đã có của discovery, tránh tạo bộ host/venue/rank thứ hai.
    session: SessionRecord


class ParticipationRepository(Protocol):
    def get_by_id(self, participation_id: int) -> Participation | None: ...

    def get_session(self, session_id: int) -> Session | None: ...

    def count_accepted(self, session_id: int) -> int: ...

    def has_active(self, user_id: int, session_id: int) -> bool: ...

    def has_overlap(self, user_id: int, starts_at: datetime, ends_at: datetime) -> bool: ...

    def create(self, data: CreateParticipationInput, now: datetime) -> Participation: ...

    def set_status(
        self, participation_id: int, status: ParticipationStatus, now: datetime
    ) -> Participation: ...

    def cancel_active_for_session(self, session_id: int, now: datetime) -> None: ...

    def list_for_session(
        self, session_id: int, *, actor_user_id: int | None = None, now: datetime | None = None
    ) -> list[ParticipationRecord]: ...

    def detail(
        self, participation_id: int, actor_user_id: int, now: datetime
    ) -> ParticipationDetail: ...
