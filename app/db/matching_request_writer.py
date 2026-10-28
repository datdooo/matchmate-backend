from collections.abc import Callable
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import MatchingRequestModel


class SqlAlchemyMatchingRequestWriter:
    """Đóng nhu cầu matching trên transaction đang xác nhận lịch chơi."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None:
        # Hai lịch nối tiếp không trùng; không sửa các nhu cầu đã CLOSED.
        self._session_provider().execute(
            update(MatchingRequestModel)
            .where(
                MatchingRequestModel.user_id == user_id,
                MatchingRequestModel.status == "ACTIVE",
                MatchingRequestModel.starts_at < ends_at,
                MatchingRequestModel.ends_at > starts_at,
            )
            .values(status="CLOSED", closed_reason="CONFIRMED", closed_at=now)
        )
        # Caller commit cùng participation/session; adapter không commit riêng.
