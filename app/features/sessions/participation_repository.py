"""SQLAlchemy adapters for the participation slice."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    MatchingRequestModel,
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.unit_of_work import DatabaseTransaction, SqlAlchemyUnitOfWork
from app.features.sessions.participation_contracts import (
    CreateParticipationInput,
    Participation,
    ParticipationError,
    ParticipationStatus,
    ParticipationTransaction,
    SessionRecord,
    UserProfile,
    VenueRecord,
)

_ACTIVE_PARTICIPATION_STATUSES = (
    ParticipationStatus.PENDING.value,
    ParticipationStatus.ACCEPTED.value,
)


def _participation_from_model(model: ParticipationModel) -> Participation:
    return Participation(
        id=model.id,
        user_id=model.user_id,
        session_id=model.session_id,
        status=model.status,
        created_at=model.created_at,
        decided_at=model.decided_at,
        cancelled_at=model.cancelled_at,
        gender_at_join=model.gender_at_join,
        quoted_fee_vnd=model.quoted_fee_vnd,
    )


def _user_from_model(model: UserModel) -> UserProfile:
    return UserProfile(
        id=model.id,
        display_name=model.display_name,
        skill_level=model.skill_level,
        gender=model.gender,
    )


class SqlAlchemyUserReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> UserProfile | None:
        model = self._session.get(UserModel, user_id)
        return None if model is None else _user_from_model(model)


class SqlAlchemySessionReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, session_id: int) -> SessionRecord | None:
        model = self._session.get(SessionModel, session_id)
        if model is None:
            return None
        host_model = self._session.get(UserModel, model.host_user_id)
        venue_model = self._session.get(VenueModel, model.venue_id)
        if host_model is None or venue_model is None:
            return None
        return SessionRecord(
            id=model.id,
            host_user_id=model.host_user_id,
            venue_id=model.venue_id,
            title=model.title,
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            play_type=model.play_type,
            fee_male_vnd=model.fee_male_vnd,
            fee_female_vnd=model.fee_female_vnd,
            min_level=model.min_level,
            max_level=model.max_level,
            gender_policy=model.gender_policy,
            status=model.status,
            host=_user_from_model(host_model),
            venue=VenueRecord(
                id=venue_model.id,
                name=venue_model.name,
                address=venue_model.address,
                district_code=venue_model.district_code,
                latitude=venue_model.latitude,
                longitude=venue_model.longitude,
            ),
        )


class SqlAlchemyParticipationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, participation_id: int) -> Participation | None:
        model = self._session.get(ParticipationModel, participation_id)
        return None if model is None else _participation_from_model(model)

    def count_accepted(self, session_id: int) -> int:
        count = self._session.scalar(
            select(func.count(ParticipationModel.id)).where(
                ParticipationModel.session_id == session_id,
                ParticipationModel.status == ParticipationStatus.ACCEPTED.value,
            )
        )
        return int(count or 0)

    def has_active(self, user_id: int, session_id: int) -> bool:
        row = self._session.scalar(
            select(ParticipationModel.id)
            .where(
                ParticipationModel.user_id == user_id,
                ParticipationModel.session_id == session_id,
                ParticipationModel.status.in_(_ACTIVE_PARTICIPATION_STATUSES),
            )
            .limit(1)
        )
        return row is not None

    def has_overlap(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        *,
        exclude_session_id: int | None = None,
    ) -> bool:
        query = (
            select(ParticipationModel.id)
            .join(SessionModel, SessionModel.id == ParticipationModel.session_id)
            .where(
                ParticipationModel.user_id == user_id,
                ParticipationModel.status == ParticipationStatus.ACCEPTED.value,
                SessionModel.starts_at < ends_at,
                SessionModel.ends_at > starts_at,
            )
        )
        if exclude_session_id is not None:
            query = query.where(SessionModel.id != exclude_session_id)
        return self._session.scalar(query.limit(1)) is not None

    def create(self, data: CreateParticipationInput, now: datetime) -> Participation:
        model = ParticipationModel(
            user_id=data.user_id,
            session_id=data.session_id,
            status=data.status,
            created_at=now,
            decided_at=data.decided_at,
            cancelled_at=None,
            gender_at_join=data.gender_at_join,
            quoted_fee_vnd=data.quoted_fee_vnd,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if self._is_active_participation_unique_violation(exc):
                raise ParticipationError(
                    "PARTICIPATION_ALREADY_EXISTS",
                    "Người chơi đã có lượt hoạt động trong kèo này",
                    {"session_id": data.session_id},
                ) from exc
            raise
        return _participation_from_model(model)

    def set_status(
        self,
        participation_id: int,
        status: str,
        now: datetime,
    ) -> Participation:
        model = self._session.get(ParticipationModel, participation_id)
        if model is None:
            raise ParticipationError(
                "PARTICIPATION_NOT_FOUND",
                "Không tìm thấy lượt tham gia",
                {"participation_id": participation_id},
            )
        model.status = status
        if status in (ParticipationStatus.ACCEPTED, ParticipationStatus.REJECTED):
            model.decided_at = now
            model.cancelled_at = None
        elif status == ParticipationStatus.CANCELLED:
            model.cancelled_at = now
        self._session.flush()
        return _participation_from_model(model)

    @staticmethod
    def _is_active_participation_unique_violation(exc: IntegrityError) -> bool:
        origin = exc.orig
        code = getattr(origin, "sqlite_errorcode", None)
        # SQLITE_CONSTRAINT is 19; extended UNIQUE is 2067. Check the primary family first.
        if not isinstance(code, int) or (code & 0xFF) != 19:
            return False
        message = str(origin)
        return (
            "participations.user_id" in message
            and "participations.session_id" in message
        ) or "uq_participations_active_user_session" in message


class SqlAlchemyMatchingRequestWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None:
        self._session.execute(
            update(MatchingRequestModel)
            .where(
                MatchingRequestModel.user_id == user_id,
                MatchingRequestModel.status == "ACTIVE",
                MatchingRequestModel.starts_at < ends_at,
                MatchingRequestModel.ends_at > starts_at,
            )
            .values(status="CLOSED", closed_reason="CONFIRMED", closed_at=now)
        )


class _ParticipationTransactionAdapter:
    def __init__(self, transaction: DatabaseTransaction) -> None:
        self._transaction = transaction
        session = transaction.session
        self.users = SqlAlchemyUserReader(session)
        self.sessions = SqlAlchemySessionReader(session)
        self.participations = SqlAlchemyParticipationRepository(session)
        self.matching = SqlAlchemyMatchingRequestWriter(session)

    def commit(self) -> None:
        self._transaction.commit()


class SQLiteParticipationUnitOfWorkFactory:
    """Bind participation repositories to the shared SQLite UoW/connection."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    @contextmanager
    def write(self) -> Iterator[ParticipationTransaction]:
        with self._uow.write() as transaction:
            yield _ParticipationTransactionAdapter(transaction)
