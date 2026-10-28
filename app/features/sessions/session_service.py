from datetime import datetime, timezone

from app.domain.enums import Gender, skill_to_rank
from app.domain.ports import Clock
from app.domain.time_rules import is_valid_time_window
from app.features.auth.contracts import UserRepository
from app.features.sessions.session_contracts import (
    CreateSessionInput,
    SessionError,
    SessionRepository,
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SessionService:
    def __init__(
        self,
        sessions: SessionRepository,
        users: UserRepository,
        clock: Clock,
    ) -> None:
        self.sessions = sessions
        self.users = users
        self.clock = clock

    def create(self, data: CreateSessionInput, host_id: int) -> int:
        # Caller phải mở uow.write() trước khi gọi phương thức này.
        now = self.clock.now()

        try:
            valid_time = is_valid_time_window(data.starts_at, data.ends_at, now)
        except ValueError:
            valid_time = False

        if not valid_time:
            raise SessionError(
                "INVALID_TIME_WINDOW",
                "Kèo phải ở tương lai và dài từ 60 đến 240 phút",
            )

        active = self.sessions.venue_is_active(data.venue_id)
        if active is None:
            raise SessionError("VENUE_NOT_FOUND", "Không tìm thấy sân")
        if not active:
            raise SessionError("VENUE_INACTIVE", "Sân đang ngừng hoạt động")

        host = self.users.get_by_id(host_id)
        if host is None:
            raise SessionError("UNAUTHORIZED", "Tài khoản không tồn tại")
        if host.gender not in (Gender.MALE, Gender.FEMALE):
            raise SessionError("PROFILE_INCOMPLETE", "Hồ sơ chưa đầy đủ")

        minimum = skill_to_rank(data.min_level)
        maximum = skill_to_rank(data.max_level)
        if minimum > maximum:
            raise SessionError("VALIDATION_ERROR", "Khoảng trình độ không hợp lệ")

        allowed_policy = ("ANY", f"{host.gender.value}_ONLY")
        if (
            not minimum <= skill_to_rank(host.skill_level) <= maximum
            or data.gender_policy not in allowed_policy
        ):
            raise SessionError(
                "ELIGIBILITY_MISMATCH",
                "Host không đáp ứng điều kiện của kèo",
            )

        if self.sessions.has_accepted_overlap(host_id, data.starts_at, data.ends_at):
            raise SessionError("TIME_CONFLICT", "Host đã có lịch chồng giờ")

        session_id = self.sessions.create_with_host(data, host, now)
        self.sessions.close_overlapping(host_id, data.starts_at, data.ends_at, now)
        return session_id
