from fastapi import Depends, Request

from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DomainError
from app.domain.ports import Clock
from app.domain.time_rules import SystemClock
from app.features.auth.contracts import DatabaseBusyError
from app.features.discovery.repository import (
    SqlAlchemyDiscoveryRepository,
    SqlAlchemyMatchingRepository,
)
from app.features.discovery.service import DiscoveryService

_session_factory = create_session_factory(engine)


def provide_clock() -> Clock:
    return SystemClock()


def provide_uow() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(
        session_factory=_session_factory, busy_error_factory=DatabaseBusyError
    )


def provide_discovery_service(
    uow: SqlAlchemyUnitOfWork = Depends(provide_uow),
    clock: Clock = Depends(provide_clock),
) -> DiscoveryService:
    return DiscoveryService(
        uow=uow,
        clock=clock,
        discovery_repo=SqlAlchemyDiscoveryRepository(uow),
        matching_repo=SqlAlchemyMatchingRepository(uow),
    )


def provide_optional_user_id(request: Request) -> int | None:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return None

    return principal.id


def provide_current_user_id(request: Request) -> int:
    user_id = provide_optional_user_id(request)
    if user_id is None:
        raise DomainError("UNAUTHORIZED", "Cần đăng nhập")

    return user_id
