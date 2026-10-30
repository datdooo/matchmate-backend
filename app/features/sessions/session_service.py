from datetime import datetime, timezone
from typing import Any

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

    def get_detail(self, session_id: int, viewer_id: int) -> dict[str, Any]:
        snapshot = self.sessions.get_detail_data(session_id)
        if snapshot is None:
            raise SessionError("SESSION_NOT_FOUND", "Không tìm thấy kèo")

        data = snapshot["session"]
        records = snapshot["participations"]
        is_host = snapshot["host_user_id"] == viewer_id
        now = self.clock.now()

        capacity = 2 if data["play_type"] == "SINGLES" else 4
        accepted_count = sum(record["status"] == "ACCEPTED" for record in records)
        available_for_changes = data["status"] == "OPEN" and now < data["starts_at"]

        for record in records:
            record["can_cancel"] = (
                available_for_changes
                and not is_host
                and record["user_id"] == viewer_id
                and record["status"] in ("PENDING", "ACCEPTED")
            )
            record["can_decide"] = (
                available_for_changes and is_host and record["status"] == "PENDING"
            )

        if data["status"] == "CANCELLED":
            display_status = "CANCELLED"
        elif now >= data["ends_at"]:
            display_status = "ENDED"
        elif now >= data["starts_at"]:
            display_status = "STARTED"
        elif accepted_count >= capacity:
            display_status = "FULL"
        else:
            display_status = "AVAILABLE"

        data.update(
            capacity=capacity,
            accepted_count=accepted_count,
            remaining_capacity=capacity - accepted_count,
            display_status=display_status,
            my_participations=[record for record in records if record["user_id"] == viewer_id],
            management={"participations": records} if is_host else None,
        )
        return data

    def cancel(self, session_id: int, actor_id: int) -> dict[str, Any]:
        snapshot = self.sessions.get_detail_data(session_id)
        if snapshot is None:
            raise SessionError("SESSION_NOT_FOUND", "Không tìm thấy kèo")

        if snapshot["host_user_id"] != actor_id:
            raise SessionError("FORBIDDEN", "Chỉ host được hủy kèo")

        if snapshot["session"]["status"] == "CANCELLED":
            return self.get_detail(session_id, actor_id)

        now = self.clock.now()
        if now >= snapshot["session"]["starts_at"]:
            raise SessionError("SESSION_ALREADY_STARTED", "Kèo đã bắt đầu")

        self.sessions.cancel_active(session_id, now)
        return self.get_detail(session_id, actor_id)
