from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import UserModel
from app.domain.enums import Gender, SkillLevel
from app.features.auth.contracts import EmailAlreadyExistsError, NewUser
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.auth.security import Argon2PasswordHasher


@pytest.fixture
def new_user() -> NewUser:
    return NewUser(
        email="player01@example.com",
        password_hash=Argon2PasswordHasher().hash("example-password"),
        display_name="Player 01",
        skill_level=SkillLevel.TB,
        gender=Gender.MALE,
        created_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
    )


def test_create_user_persists_after_commit(
    db_session_factory: sessionmaker[Session],
    new_user: NewUser,
) -> None:
    with db_session_factory.begin() as session:
        repository = SqlAlchemyUserRepository(session)
        user = repository.create(new_user)

        assert user.id > 0

    # Mở session khác để kiểm dữ liệu đã được commit.
    with db_session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        loaded = repository.get_by_email(new_user.email)

        assert loaded == user

        model = session.scalar(select(UserModel).where(UserModel.id == user.id))

        assert model is not None
        assert model.skill_level == 9
        assert model.gender == "MALE"
        assert model.created_at == new_user.created_at
        assert model.updated_at == new_user.created_at
        assert Argon2PasswordHasher().verify("example-password", model.password_hash)


def test_duplicate_email_rolls_back(
    db_session_factory: sessionmaker[Session],
    new_user: NewUser,
) -> None:
    with db_session_factory.begin() as session:
        SqlAlchemyUserRepository(session).create(new_user)

    with pytest.raises(EmailAlreadyExistsError):
        with db_session_factory.begin() as session:
            SqlAlchemyUserRepository(session).create(new_user)

    with db_session_factory() as session:
        count = session.scalar(select(func.count()).select_from(UserModel))

        assert count == 1
