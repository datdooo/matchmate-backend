import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ParticipationModel, SessionModel, UserModel, VenueModel
from app.domain.entities import Participation
from app.domain.entities import Session as Game
from app.domain.enums import (
    DisplayStatus,
    Gender,
    GenderPolicy,
    ParticipationStatus,
    PlayType,
    SessionStatus,
)
from app.domain.errors import DomainError
from app.features.auth.contracts import User
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.discovery.contracts import PlayerSummary, SessionRecord, VenueRecord
from app.features.sessions.participation_contracts import (
    CreateParticipationInput,
    ParticipationDetail,
    ParticipationRecord,
)
from app.features.sessions.participation_mapper import to_participation_record


class SqlAlchemyParticipationRepository:
    """Các query dùng Session của UoW hiện tại, không mở connection riêng."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def get_user(self, user_id: int) -> User | None:
        return SqlAlchemyUserRepository(self._session_provider()).get_by_id(user_id)

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

    def get_by_id(self, participation_id: int) -> Participation | None:
        model = self._session_provider().get(ParticipationModel, participation_id)
        return to_participation(model) if model is not None else None

    def get_session(self, session_id: int) -> Game | None:
        model = self._session_provider().get(SessionModel, session_id)
        if model is None:
            return None
        return Game(
            id=model.id,
            host_user_id=model.host_user_id,
            venue_id=model.venue_id,
            title=model.title,
            notes=model.notes,
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            play_type=PlayType(model.play_type),
            fee_male_vnd=model.fee_male_vnd,
            fee_female_vnd=model.fee_female_vnd,
            min_level=model.min_level,
            max_level=model.max_level,
            gender_policy=GenderPolicy(model.gender_policy),
            status=SessionStatus(model.status),
            created_at=model.created_at,
            cancelled_at=model.cancelled_at,
        )

    def create(self, data: CreateParticipationInput, now: datetime) -> Participation:
        model = ParticipationModel(
            user_id=data.user_id,
            session_id=data.session_id,
            status=data.status.value,
            gender_at_join=data.gender_at_join.value,
            quoted_fee_vnd=data.quoted_fee_vnd,
            created_at=now,
            decided_at=now if data.status == ParticipationStatus.ACCEPTED else None,
        )
        session = self._session_provider()
        session.add(model)
        try:
            session.flush()
        except IntegrityError as error:
            # Chỉ unique đúng hai cột này là trùng lượt; FK/CHECK vẫn là lỗi kỹ thuật.
            if getattr(
                error.orig, "sqlite_errorcode", None
            ) == sqlite3.SQLITE_CONSTRAINT_UNIQUE and str(error.orig) == (
                "UNIQUE constraint failed: participations.user_id, participations.session_id"
            ):
                raise DomainError(
                    "PARTICIPATION_ALREADY_EXISTS", "Đã có lượt tham gia đang hoạt động"
                ) from error
            raise
        return to_participation(model)

    def set_status(
        self, participation_id: int, status: ParticipationStatus, now: datetime
    ) -> Participation:
        session = self._session_provider()
        model = session.get(ParticipationModel, participation_id)
        if model is None:
            raise DomainError("PARTICIPATION_NOT_FOUND", "Không tìm thấy lượt tham gia")
        if status == ParticipationStatus.CANCELLED:
            model.cancelled_at = now
        elif status in (ParticipationStatus.ACCEPTED, ParticipationStatus.REJECTED):
            model.decided_at = now
        else:
            raise ValueError("Không mở lại lượt cũ; đăng ký lại phải tạo bản ghi mới")
        model.status = status.value
        session.flush()
        return to_participation(model)

    def cancel_active_for_session(self, session_id: int, now: datetime) -> None:
        # Hủy cả host và player, giữ nguyên snapshot phí/giới tính và decided_at cũ.
        self._session_provider().execute(
            update(ParticipationModel)
            .where(
                ParticipationModel.session_id == session_id,
                ParticipationModel.status.in_(("PENDING", "ACCEPTED")),
            )
            .values(status="CANCELLED", cancelled_at=now)
        )

    def list_for_session(
        self, session_id: int, *, actor_user_id: int | None = None, now: datetime | None = None
    ) -> list[ParticipationRecord]:
        """Không có ngữ cảnh người xem thì các cờ quyền đều bằng False."""
        game = self.get_session(session_id)
        if game is None:
            return []
        rows = self._session_provider().execute(
            select(ParticipationModel, UserModel)
            .join(UserModel, UserModel.id == ParticipationModel.user_id)
            .where(ParticipationModel.session_id == session_id)
            .order_by(ParticipationModel.created_at, ParticipationModel.id)
        )
        return [
            to_participation_record(
                to_participation(part), game, to_player(user), actor_user_id, now
            )
            for part, user in rows
        ]

    def detail(
        self, participation_id: int, actor_user_id: int, now: datetime
    ) -> ParticipationDetail:
        part = self.get_by_id(participation_id)
        if part is None:
            raise DomainError("PARTICIPATION_NOT_FOUND", "Không tìm thấy lượt tham gia")
        game = self.get_session(part.session_id)
        session = self._session_provider()
        user = session.get(UserModel, part.user_id)
        host = session.get(UserModel, game.host_user_id)
        venue = session.get(VenueModel, game.venue_id)
        accepted = self.count_accepted(game.id)
        if game.status == SessionStatus.CANCELLED:
            display = DisplayStatus.CANCELLED
        elif now >= game.ends_at:
            display = DisplayStatus.ENDED
        elif now >= game.starts_at:
            display = DisplayStatus.STARTED
        elif accepted >= game.capacity:
            display = DisplayStatus.FULL
        else:
            display = DisplayStatus.AVAILABLE
        summary = SessionRecord(
            id=game.id,
            host=to_player(host),
            venue=VenueRecord(
                venue.id, venue.name, venue.address, venue.district_code, venue.is_active
            ),
            title=game.title,
            notes=game.notes,
            starts_at=game.starts_at,
            ends_at=game.ends_at,
            play_type=game.play_type,
            fee_male_vnd=game.fee_male_vnd,
            fee_female_vnd=game.fee_female_vnd,
            min_level=game.min_level,
            max_level=game.max_level,
            gender_policy=game.gender_policy,
            status=game.status,
            capacity=game.capacity,
            accepted_count=accepted,
            remaining_capacity=game.capacity - accepted,
            display_status=display,
        )
        record = to_participation_record(part, game, to_player(user), actor_user_id, now)
        # asdict(record) chuyển player thành dict; giữ DTO player thuần để các caller dùng lại.
        values = asdict(part)
        return ParticipationDetail(
            **values,
            player=record.player,
            can_cancel=record.can_cancel,
            can_decide=record.can_decide,
            session=summary,
        )


def to_participation(model: ParticipationModel) -> Participation:
    return Participation(
        id=model.id,
        user_id=model.user_id,
        session_id=model.session_id,
        status=ParticipationStatus(model.status),
        gender_at_join=Gender(model.gender_at_join),
        quoted_fee_vnd=model.quoted_fee_vnd,
        created_at=model.created_at,
        decided_at=model.decided_at,
        cancelled_at=model.cancelled_at,
    )


def to_player(model: UserModel) -> PlayerSummary:
    return PlayerSummary(model.id, model.display_name, model.skill_level, Gender(model.gender))
