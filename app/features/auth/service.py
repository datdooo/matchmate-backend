from datetime import datetime, timezone

from app.domain.enums import Gender, SkillLevel
from app.features.auth.contracts import (
    AccessToken,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    NewUser,
    PasswordHasher,
    TokenIssuer,
    User,
    UserRepository,
)


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self.user_repository = user_repository
        self.password_hasher = password_hasher

    def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        skill_level: SkillLevel,
        gender: Gender,
    ) -> User:
        email = email.strip().lower()

        if self.user_repository.get_by_email(email) is not None:
            raise EmailAlreadyExistsError()

        password_hash = self.password_hasher.hash(password)

        new_user = NewUser(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            skill_level=skill_level,
            gender=gender,
            created_at=datetime.now(timezone.utc),
        )

        return self.user_repository.create(new_user)

    def authenticate(self, *, email: str, password: str) -> int:
        email = email.strip().lower()

        credentials = self.user_repository.get_credentials_by_email(email)

        if credentials is None:
            raise InvalidCredentialsError()

        password_matches = self.password_hasher.verify(
            password,
            credentials.password_hash,
        )

        if not password_matches:
            raise InvalidCredentialsError()

        return credentials.user_id

    def login(
        self,
        *,
        email: str,
        password: str,
        token_issuer: TokenIssuer,
    ) -> AccessToken:
        user_id = self.authenticate(email=email, password=password)
        return token_issuer.issue(user_id)
