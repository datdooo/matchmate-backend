from app.domain.enums import Gender, SkillLevel
from app.features.auth.contracts import (
    EmailAlreadyExistsError,
    NewUser,
    PasswordHasher,
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
        )

        return self.user_repository.create(new_user)
