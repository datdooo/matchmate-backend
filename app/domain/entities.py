"""Dữ liệu nghiệp vụ thuần; không giữ ORM hoặc DB Session sau transaction."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import (
    DisplayStatus,
    Gender,
    GenderPolicy,
    ParticipationStatus,
    PlayType,
    SessionStatus,
)


def compute_display_status(
    status: SessionStatus,
    starts_at: datetime,
    ends_at: datetime,
    accepted_count: int,
    capacity: int,
    now: datetime,
) -> DisplayStatus:
    """Trạng thái hiển thị dùng chung cho tìm kèo, chi tiết và lượt tham gia."""
    if status == SessionStatus.CANCELLED:
        return DisplayStatus.CANCELLED
    if now >= ends_at:
        return DisplayStatus.ENDED
    if now >= starts_at:
        return DisplayStatus.STARTED
    if accepted_count >= capacity:
        return DisplayStatus.FULL
    return DisplayStatus.AVAILABLE


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
