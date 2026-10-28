from datetime import datetime, timedelta, timezone

import jwt

from app.features.auth.contracts import AccessToken


class JwtTokenIssuer:
    def __init__(
        self,
        secret_key: str,
        ttl_seconds: int = 3600,
    ) -> None:
        if len(secret_key.encode("utf-8")) < 32:
            raise ValueError("JWT secret must contain at least 32 bytes")

        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("Token lifetime must be a positive integer")

        self.secret_key = secret_key
        self.ttl_seconds = ttl_seconds

    def issue(self, user_id: int) -> AccessToken:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("User ID must be a positive integer")

        now = datetime.now(timezone.utc)

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=self.ttl_seconds),
        }

        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm="HS256",
        )

        return AccessToken(
            access_token=token,
            expires_in=self.ttl_seconds,
        )
