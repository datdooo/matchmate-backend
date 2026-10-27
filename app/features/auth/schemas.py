from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.enums import Gender, SkillLevel


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(strict=True, min_length=8, max_length=128)
    display_name: str = Field(strict=True, min_length=1, max_length=80)
    skill_level: SkillLevel
    gender: Literal[Gender.MALE, Gender.FEMALE]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class UserSelf(BaseModel):
    id: int = Field(gt=0)
    email: EmailStr
    display_name: str
    skill_level: SkillLevel
    gender: Gender


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(strict=True)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class TokenData(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)
