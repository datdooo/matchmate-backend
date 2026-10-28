from collections.abc import Iterator

from app.config import load_settings
from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError, User
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.auth.security import Argon2PasswordHasher
from app.features.auth.service import AuthService
from app.features.auth.tokens import JwtTokenIssuer

_session_factory = create_session_factory(engine)


def provide_registration_service() -> Iterator[AuthService]:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    with uow.write():
        repository = SqlAlchemyUserRepository(uow.session)
        service = AuthService(
            user_repository=repository,
            password_hasher=Argon2PasswordHasher(),
        )

        yield service

        uow.commit()


def provide_login_service() -> Iterator[AuthService]:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    with uow.read():
        yield AuthService(
            user_repository=SqlAlchemyUserRepository(uow.session),
            password_hasher=Argon2PasswordHasher(),
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
        return SqlAlchemyUserRepository(uow.session).get_by_id(user_id)
