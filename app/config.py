import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    jwt_secret_key: str
    access_token_expire_seconds: int


def load_settings() -> Settings:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, override=False)

    secret = os.environ.get("JWT_SECRET_KEY", "")
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    minutes = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    if len(secret.encode("utf-8")) < 32:
        raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes")

    if algorithm != "HS256":
        raise ValueError("Only HS256 is supported")

    if minutes <= 0:
        raise ValueError("Token lifetime must be positive")

    return Settings(
        jwt_secret_key=secret,
        access_token_expire_seconds=minutes * 60,
    )
