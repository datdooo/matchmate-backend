from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ParticipationModel, SessionModel, UserModel
from app.domain.enums import rank_to_skill
from app.features.catalog.contracts import VenueReader


class SqlAlchemySessionDetailReader:
    def __init__(self, session_provider: Callable[[], Session], venues: VenueReader) -> None:
        self._session_provider = session_provider
        self._venues = venues

    @staticmethod
    def _player_summary(model: UserModel) -> dict[str, Any]:
        return {
            "id": model.id,
            "display_name": model.display_name,
            "skill_level": rank_to_skill(model.skill_level),
            "gender": model.gender,
        }

    def get_detail_data(self, session_id: int) -> dict[str, Any] | None:
        session = self._session_provider()
        model = session.get(SessionModel, session_id)
        if model is None:
            return None

        host = session.get(UserModel, model.host_user_id)
        venue = self._venues.get_by_id(model.venue_id)
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
        for participation, player in session.execute(statement):
            record = {name: getattr(participation, name) for name in participation_fields}
            record["player"] = self._player_summary(player)
            records.append(record)

        return {
            "session": data,
            "host_user_id": model.host_user_id,
            "participations": records,
        }
