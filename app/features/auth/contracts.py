from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.enums import Gender, SkillLevel


@dataclass(frozen=True)
class User:
    id: int
    email: str
    display_name: str
    skill_level: SkillLevel
    gender: Gender


@dataclass(frozen=True)
class NewUser:
    email: str
    password_hash: str
    display_name: str
    skill_level: SkillLevel
    gender: Gender
    created_at: datetime


class EmailAlreadyExistsError(Exception):
    """Email da dc dang ki"""


@dataclass(frozen=True)
class UserCredentials:
    user_id: int
    password_hash: str


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def create(self, data: NewUser) -> User:
        """Luu user, raise EmailAlreadyExistsError neu email trung"""
        ...

    def get_credentials_by_email(
        self,
        email: str,
    ) -> UserCredentials | None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class DatabaseBusyError(Exception):
    """Không lấy được khóa ghi DB trong thời gian cho phép."""


class InvalidCredentialsError(Exception):
    """Email hoặc mật khẩu không đúng."""


@dataclass(frozen=True)
class AccessToken:
    access_token: str
    expires_in: int
    token_type: str = "bearer"


class TokenIssuer(Protocol):
    def issue(self, user_id: int) -> AccessToken: ...
