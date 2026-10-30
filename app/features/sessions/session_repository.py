from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.models import (
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.domain.enums import Gender, rank_to_skill, skill_to_rank
from app.features.auth.contracts import User
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
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

    @staticmethod
    def _player_summary(model: UserModel) -> dict[str, Any]:
        return {
            "id": model.id,
            "display_name": model.display_name,
            "skill_level": rank_to_skill(model.skill_level),
            "gender": model.gender,
        }

    def get_detail_data(self, session_id: int) -> dict[str, Any] | None:
        model = self.session.get(SessionModel, session_id)
        if model is None:
            return None

        host = self.session.get(UserModel, model.host_user_id)
        venue = self.session.get(VenueModel, model.venue_id)
        if host is None or venue is None:
            raise RuntimeError("Session references missing host or venue")

        fields = (
            "id",
            "title",
            "notes",
            "starts_at",
            "ends_at",
            "play_type",
            "fee_male_vnd",
            "fee_female_vnd",
            "gender_policy",
            "status",
            "created_at",
            "cancelled_at",
        )
        data = {name: getattr(model, name) for name in fields}
        data.update(
            host=self._player_summary(host),
            venue={
                "id": venue.id,
                "name": venue.name,
                "address": venue.address,
                "district_code": venue.district_code,
                "is_active": venue.is_active,
            },
            min_level=rank_to_skill(model.min_level),
            max_level=rank_to_skill(model.max_level),
        )

        statement = (
            select(ParticipationModel, UserModel)
            .select_from(ParticipationModel)
            .join(UserModel, ParticipationModel.user_id == UserModel.id)
            .where(ParticipationModel.session_id == session_id)
            .order_by(
                ParticipationModel.created_at.desc(),
                ParticipationModel.id.desc(),
            )
        )

        participation_fields = (
            "id",
            "user_id",
            "session_id",
            "status",
            "created_at",
            "decided_at",
            "cancelled_at",
            "gender_at_join",
            "quoted_fee_vnd",
        )
        records = []
        for participation, player in self.session.execute(statement):
            record = {name: getattr(participation, name) for name in participation_fields}
            record["player"] = self._player_summary(player)
            records.append(record)

        return {
            "session": data,
            "host_user_id": model.host_user_id,
            "participations": records,
        }

    def cancel_active(self, session_id: int, now: datetime) -> None:
        self.session.execute(
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(status="CANCELLED", cancelled_at=now)
        )

        # Cùng Session với UPDATE kèo; caller commit cả hai bước một lần.
        SqlAlchemyParticipationRepository(lambda: self.session).cancel_active_for_session(
            session_id, now
        )
