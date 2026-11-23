from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import ParticipationModel, SessionModel
from app.domain.enums import Gender, skill_to_rank
from app.features.auth.contracts import PlayerProfile
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.session_contracts import CreateSessionInput


class SqlAlchemySessionRepository:
    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def create_with_host(
        self,
        data: CreateSessionInput,
        host: PlayerProfile,
        now: datetime,
    ) -> int:
        quoted_fee = {
            Gender.MALE: data.fee_male_vnd,
            Gender.FEMALE: data.fee_female_vnd,
        }[host.gender]

        model = SessionModel(
            host_user_id=host.id,
            venue_id=data.venue_id,
            title=data.title,
            notes=data.notes,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            play_type=data.play_type,
            fee_male_vnd=data.fee_male_vnd,
            fee_female_vnd=data.fee_female_vnd,
            min_level=skill_to_rank(data.min_level),
            max_level=skill_to_rank(data.max_level),
            gender_policy=data.gender_policy,
            status="OPEN",
            created_at=now,
        )
        session = self._session_provider()
        session.add(model)
        session.flush()

        session.add(
            ParticipationModel(
                user_id=host.id,
                session_id=model.id,
                status="ACCEPTED",
                gender_at_join=host.gender.value,
                quoted_fee_vnd=quoted_fee,
                created_at=now,
                decided_at=now,
            )
        )
        session.flush()

        return model.id

    def has_accepted_overlap(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        statement = (
            select(ParticipationModel.id)
            .join(SessionModel, ParticipationModel.session_id == SessionModel.id)
            .where(
                ParticipationModel.user_id == user_id,
                ParticipationModel.status == "ACCEPTED",
                SessionModel.status == "OPEN",
                SessionModel.starts_at < ends_at,
                SessionModel.ends_at > starts_at,
            )
            .limit(1)
        )
        return self._session_provider().scalar(statement) is not None

    def cancel_active(self, session_id: int, now: datetime) -> None:
        self._session_provider().execute(
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(status="CANCELLED", cancelled_at=now)
        )

        # Cùng Session với UPDATE kèo; caller commit cả hai bước một lần.
        SqlAlchemyParticipationRepository(self._session_provider).cancel_active_for_session(
            session_id, now
        )
