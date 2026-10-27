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


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> User | None: ...

    def create(self, data: NewUser) -> User:
        """Luu user, raise EmailAlreadyExistsError neu email trung"""
        ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class DatabaseBusyError(Exception):
    """Không lấy được khóa ghi DB trong thời gian cho phép."""
