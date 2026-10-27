import sqlite3

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import UserModel
from app.domain.enums import Gender, rank_to_skill, skill_to_rank
from app.features.auth.contracts import (
    EmailAlreadyExistsError,
    NewUser,
    User,
    UserCredentials,
)


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        statement = select(UserModel).where(UserModel.email == email)
        model = self.session.scalar(statement)

        if model is None:
            return None

        return User(
            id=model.id,
            email=model.email,
            display_name=model.display_name,
            skill_level=rank_to_skill(model.skill_level),
            gender=Gender(model.gender),
        )

    def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None:
        statement = select(UserModel).where(UserModel.email == email)
        model = self.session.scalar(statement)

        if model is None:
            return None

        return UserCredentials(
            user_id=model.id,
            password_hash=model.password_hash,
        )

    def create(self, data: NewUser) -> User:
        model = UserModel(
            email=data.email,
            password_hash=data.password_hash,
            display_name=data.display_name,
            skill_level=skill_to_rank(data.skill_level),
            gender=data.gender.value,
            created_at=data.created_at,
            updated_at=data.created_at,
        )

        self.session.add(model)

        try:
            self.session.flush()
        except IntegrityError as exc:
            is_duplicate_email = (
                getattr(exc.orig, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_UNIQUE
                and str(exc.orig) == "UNIQUE constraint failed: users.email"
            )

            if is_duplicate_email:
                raise EmailAlreadyExistsError() from exc
            raise

        return User(
            id=model.id,
            email=model.email,
            display_name=model.display_name,
            skill_level=rank_to_skill(model.skill_level),
            gender=Gender(model.gender),
        )

    def get_by_id(self, user_id: int) -> User | None:
        model = self.session.get(UserModel, user_id)
        if model is None:
            return None

        return User(
            id=model.id,
            email=model.email,
            display_name=model.display_name,
            skill_level=rank_to_skill(model.skill_level),
            gender=Gender(model.gender),
        )
