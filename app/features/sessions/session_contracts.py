from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from app.domain.enums import SkillLevel
from app.features.auth.contracts import PlayerProfile


@dataclass(frozen=True)
class CreateSessionInput:
    venue_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    play_type: Literal["SINGLES", "DOUBLES"]
    fee_male_vnd: int
    fee_female_vnd: int
    min_level: SkillLevel
    max_level: SkillLevel
    notes: str = ""
    gender_policy: Literal["ANY", "MALE_ONLY", "FEMALE_ONLY"] = "ANY"


class SessionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SessionRepository(Protocol):
    def has_accepted_overlap(
        self, user_id: int, starts_at: datetime, ends_at: datetime
    ) -> bool: ...

    def create_with_host(
        self, data: CreateSessionInput, host: PlayerProfile, now: datetime
    ) -> int: ...

    def cancel_active(self, session_id: int, now: datetime) -> None: ...


class SessionDetailReader(Protocol):
    def get_detail_data(self, session_id: int) -> dict[str, Any] | None: ...
