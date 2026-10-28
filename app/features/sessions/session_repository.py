from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.models import (
    ParticipationModel,
    SessionModel,
    VenueModel,
)
from app.domain.enums import Gender, skill_to_rank
from app.features.auth.contracts import User
from app.features.sessions.session_contracts import CreateSessionInput


class SqlAlchemySessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_with_host(
        self,
        data: CreateSessionInput,
        host: User,
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
        self.session.add(model)
        self.session.flush()

        self.session.add(
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
        self.session.flush()

        return model.id

    def venue_is_active(self, venue_id: int) -> bool | None:
        return self.session.scalar(select(VenueModel.is_active).where(VenueModel.id == venue_id))

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
        return self.session.scalar(statement) is not None

    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None:
        SqlAlchemyMatchingRequestWriter(lambda: self.session).close_overlapping(
            user_id, starts_at, ends_at, now
        )
