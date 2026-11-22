from collections.abc import Callable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserModel
from app.domain.enums import Gender, rank_to_skill
from app.features.auth.contracts import PlayerProfile

_COLUMNS = (UserModel.id, UserModel.display_name, UserModel.skill_level, UserModel.gender)


def to_profile(row: Mapping) -> PlayerProfile:
    return PlayerProfile(
        id=row["id"],
        display_name=row["display_name"],
        skill_level=rank_to_skill(row["skill_level"]),
        gender=Gender(row["gender"]),
    )


class SqlAlchemyPlayerProfileReader:
    """Identity's public projection, in the caller's transaction; no credentials."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def get_by_id(self, user_id: int) -> PlayerProfile | None:
        row = (
            self._session_provider()
            .execute(select(*_COLUMNS).where(UserModel.id == user_id))
            .mappings()
            .one_or_none()
        )
        return to_profile(row) if row is not None else None

    def get_by_ids(self, user_ids: list[int]) -> dict[int, PlayerProfile]:
        ids = list(dict.fromkeys(user_ids))
        if not ids:
            return {}
        session = self._session_provider()
        result = {}
        for offset in range(0, len(ids), 500):
            rows = session.execute(
                select(*_COLUMNS).where(UserModel.id.in_(ids[offset : offset + 500]))
            ).mappings()
            for row in rows:
                profile = to_profile(row)
                result[profile.id] = profile
        return result
