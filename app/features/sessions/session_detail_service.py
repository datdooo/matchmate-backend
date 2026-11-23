from typing import Any

from app.domain.entities import compute_display_status
from app.domain.enums import SessionStatus
from app.domain.ports import Clock, UnitOfWork
from app.features.sessions.session_contracts import SessionDetailReader, SessionError


class SessionDetailService:
    def __init__(self, uow: UnitOfWork, details: SessionDetailReader, clock: Clock) -> None:
        self.uow = uow
        self.details = details
        self.clock = clock

    def get_detail(self, session_id: int, viewer_id: int) -> dict[str, Any]:
        with self.uow.read():
            return build_session_detail(
                self.details.get_detail_data(session_id), viewer_id, self.clock
            )


def build_session_detail(
    snapshot: dict[str, Any] | None, viewer_id: int, clock: Clock
) -> dict[str, Any]:
    if snapshot is None:
        raise SessionError("SESSION_NOT_FOUND", "Không tìm thấy kèo")

    data = snapshot["session"]
    records = snapshot["participations"]
    is_host = snapshot["host_user_id"] == viewer_id
    now = clock.now()

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
        record["can_decide"] = available_for_changes and is_host and record["status"] == "PENDING"

    data.update(
        capacity=capacity,
        accepted_count=accepted_count,
        remaining_capacity=capacity - accepted_count,
        display_status=compute_display_status(
            SessionStatus(data["status"]),
            data["starts_at"],
            data["ends_at"],
            accepted_count,
            capacity,
            now,
        ),
        my_participations=[record for record in records if record["user_id"] == viewer_id],
        management={"participations": records} if is_host else None,
    )
    return data
