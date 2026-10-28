import pytest

from app.domain.enums import Gender, SkillLevel
from app.features.auth.contracts import (
    EmailAlreadyExistsError,
    NewUser,
    User,
)
from app.features.auth.security import Argon2PasswordHasher
from app.features.auth.service import AuthService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.saved_data: NewUser | None = None

    def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    def create(self, data: NewUser) -> User:
        if data.email in self.users:
            raise EmailAlreadyExistsError()

        user = User(
            id=len(self.users) + 1,
            email=data.email,
            display_name=data.display_name,
            skill_level=data.skill_level,
            gender=data.gender,
            created_at=data.created_at,
            updated_at=data.created_at,
        )
        self.users[data.email] = user
        self.saved_data = data
        return user


def test_registers_stores_password_hash() -> None:
    repository = FakeUserRepository()
    hasher = Argon2PasswordHasher()
    service = AuthService(repository, hasher)

    user = service.register(
        email=" Player01@example.com ",
        password="example-password",
        display_name="Player 01",
        skill_level=SkillLevel.TB,
        gender=Gender.MALE,
    )

    assert user.id == 1
    assert user.email == "player01@example.com"
    assert user.display_name == "Player 01"
    assert user.skill_level == SkillLevel.TB
    assert user.gender == Gender.MALE

    saved = repository.saved_data
    assert saved is not None
    assert saved.password_hash != "example-password"
    assert hasher.verify("example-password", saved.password_hash)
    assert not hasher.verify("wrong_password", saved.password_hash)


def test_register_rejects_duplicate_email() -> None:
    repository = FakeUserRepository()
    service = AuthService(repository, Argon2PasswordHasher())

    service.register(
        email="player01@example.com",
        password="example-password",
        display_name="Player 01",
        skill_level=SkillLevel.TB,
        gender=Gender.MALE,
    )

    with pytest.raises(EmailAlreadyExistsError):
        service.register(
            email="PLAYER01@EXAMPLE.com",
            password="another-password",
            display_name="Player 02",
            skill_level=SkillLevel.TB,
            gender=Gender.FEMALE,
        )

    assert len(repository.users) == 1
