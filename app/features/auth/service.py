from datetime import datetime, timezone

from app.domain.enums import Gender, SkillLevel
from app.domain.ports import UnitOfWork
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
        uow: UnitOfWork,
    ) -> None:
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.uow = uow

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
        password_hash = self.password_hasher.hash(password)

        with self.uow.write():
            if self.user_repository.get_by_email(email) is not None:
                raise EmailAlreadyExistsError()

            new_user = NewUser(
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                skill_level=skill_level,
                gender=gender,
                created_at=datetime.now(timezone.utc),
            )

            user = self.user_repository.create(new_user)
            self.uow.commit()
            return user

    def authenticate(self, *, email: str, password: str) -> int:
        email = email.strip().lower()

        with self.uow.read():
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
