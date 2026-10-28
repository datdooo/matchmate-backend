from dataclasses import asdict
from datetime import datetime

from app.domain.entities import Participation, Session
from app.domain.enums import ParticipationStatus, SessionStatus
from app.features.discovery.contracts import PlayerSummary
from app.features.sessions.participation_contracts import ParticipationRecord


def to_participation_record(
    participation: Participation,
    session: Session,
    player: PlayerSummary,
    actor_user_id: int | None,
    now: datetime | None,
) -> ParticipationRecord:
    """Cờ quyền chỉ phục vụ hiển thị; Service vẫn kiểm lại lúc thao tác."""
    before_start = now is not None and now < session.starts_at
    editable = session.status == SessionStatus.OPEN and before_start
    return ParticipationRecord(
        **asdict(participation),
        player=player,
        can_cancel=(
            editable
            and actor_user_id == participation.user_id
            and actor_user_id != session.host_user_id
            and participation.status in (ParticipationStatus.PENDING, ParticipationStatus.ACCEPTED)
        ),
        can_decide=(
            editable
            and actor_user_id == session.host_user_id
            and participation.status == ParticipationStatus.PENDING
        ),
    )
