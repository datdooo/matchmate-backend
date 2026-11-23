from app.config import load_settings
from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DatabaseBusyError
from app.features.auth.contracts import User
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.auth.security import Argon2PasswordHasher
from app.features.auth.service import AuthService
from app.features.auth.tokens import JwtTokenIssuer

_session_factory = create_session_factory(engine)


def provide_auth_service() -> AuthService:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    return AuthService(
        user_repository=SqlAlchemyUserRepository(lambda: uow.session),
        password_hasher=Argon2PasswordHasher(),
        uow=uow,
    )


def provide_token_issuer() -> JwtTokenIssuer:
    settings = load_settings()
    return JwtTokenIssuer(
        secret_key=settings.jwt_secret_key,
        ttl_seconds=settings.access_token_expire_seconds,
    )


def lookup_authenticated_user(user_id: int) -> User | None:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    with uow.read():
        return SqlAlchemyUserRepository(lambda: uow.session).get_by_id(user_id)
