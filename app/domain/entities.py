"""Dữ liệu nghiệp vụ thuần; không giữ ORM hoặc DB Session sau transaction."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import Gender, GenderPolicy, ParticipationStatus, PlayType, SessionStatus


@dataclass(frozen=True)
class Session:
    id: int
    host_user_id: int
    venue_id: int
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
    created_at: datetime
    cancelled_at: datetime | None

    @property
    def capacity(self) -> int:
        """Sức chứa gồm host; không lưu counter riêng trong DB."""
        return 2 if self.play_type == PlayType.SINGLES else 4


@dataclass(frozen=True)
class Participation:
    id: int
    user_id: int
    session_id: int
    status: ParticipationStatus
    gender_at_join: Gender
    quoted_fee_vnd: int
    created_at: datetime
    decided_at: datetime | None
    cancelled_at: datetime | None
