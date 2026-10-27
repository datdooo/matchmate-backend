from collections.abc import Iterator

from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.auth.security import Argon2PasswordHasher
from app.features.auth.service import AuthService

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
