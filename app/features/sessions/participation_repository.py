from collections.abc import Callable
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.db.models import ParticipationModel, SessionModel


class SqlAlchemyParticipationRepository:
    """Các query dùng Session của UoW hiện tại, không mở connection riêng."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def count_accepted(self, session_id: int) -> int:
        return self._session_provider().scalar(
            select(func.count())
            .select_from(ParticipationModel)
            .where(
                ParticipationModel.session_id == session_id,
                ParticipationModel.status == "ACCEPTED",
            )
        )

    def has_active(self, user_id: int, session_id: int) -> bool:
        return self._session_provider().scalar(
            select(
                exists().where(
                    ParticipationModel.user_id == user_id,
                    ParticipationModel.session_id == session_id,
                    ParticipationModel.status.in_(("PENDING", "ACCEPTED")),
                )
            )
        )

    def has_overlap(self, user_id: int, starts_at: datetime, ends_at: datetime) -> bool:
        # PENDING chưa xác nhận lịch. Chỉ ACCEPTED mới chặn một buổi khác.
        statement = (
            select(ParticipationModel.id)
            .join(SessionModel, ParticipationModel.session_id == SessionModel.id)
            .where(
                ParticipationModel.user_id == user_id,
                ParticipationModel.status == "ACCEPTED",
                SessionModel.starts_at < ends_at,
                SessionModel.ends_at > starts_at,
            )
            .limit(1)
        )
        return self._session_provider().scalar(statement) is not None
