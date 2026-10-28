from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.security import HTTPBearer

from app.api.schemas import ErrorResponse
from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.sessions.session_repository import SqlAlchemySessionRepository
from app.features.sessions.session_schemas import CreateSessionRequest, SessionDetail
from app.features.sessions.session_service import SessionService, SystemClock

router = APIRouter(tags=["Sessions"])
_bearer = HTTPBearer(auto_error=False)
_session_factory = create_session_factory(engine)


def provide_create_session_service() -> Iterator[SessionService]:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    with uow.write():
        yield SessionService(
            sessions=SqlAlchemySessionRepository(uow.session),
            users=SqlAlchemyUserRepository(uow.session),
            clock=SystemClock(),
        )
        uow.commit()


def provide_read_session_service() -> Iterator[SessionService]:
    uow = SqlAlchemyUnitOfWork(
        session_factory=_session_factory,
        busy_error_factory=DatabaseBusyError,
    )

    with uow.read():
        yield SessionService(
            sessions=SqlAlchemySessionRepository(uow.session),
            users=SqlAlchemyUserRepository(uow.session),
            clock=SystemClock(),
        )


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_bearer)],
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHORIZED"},
        404: {"model": ErrorResponse, "description": "VENUE_NOT_FOUND"},
        409: {"model": ErrorResponse, "description": "Xung đột nghiệp vụ"},
        422: {"model": ErrorResponse, "description": "Dữ liệu không hợp lệ"},
        503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
    },
)
def create_session(
    payload: CreateSessionRequest,
    request: Request,
    service: SessionService = Depends(
        provide_create_session_service,
        scope="function",
    ),
) -> SessionDetail:
    session_id = service.create(
        data=payload.to_input(),
        host_id=request.state.principal.id,
    )
    return SessionDetail.model_validate(service.get_detail(session_id, request.state.principal.id))


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    dependencies=[Depends(_bearer)],
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHORIZED"},
        404: {"model": ErrorResponse, "description": "SESSION_NOT_FOUND"},
        422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
        503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
    },
)
def get_session_detail(
    session_id: Annotated[int, Path(gt=0, le=9223372036854775807)],
    request: Request,
    service: SessionService = Depends(
        provide_read_session_service,
        scope="function",
    ),
) -> SessionDetail:
    return SessionDetail.model_validate(service.get_detail(session_id, request.state.principal.id))


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_bearer)],
    responses={
        401: {"model": ErrorResponse, "description": "UNAUTHORIZED"},
        403: {"model": ErrorResponse, "description": "FORBIDDEN"},
        404: {"model": ErrorResponse, "description": "SESSION_NOT_FOUND"},
        409: {"model": ErrorResponse, "description": "SESSION_ALREADY_STARTED"},
        422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
        503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
    },
)
def cancel_session(
    session_id: Annotated[int, Path(gt=0, le=9223372036854775807)],
    request: Request,
    service: SessionService = Depends(
        provide_create_session_service,
        scope="function",
    ),
) -> SessionDetail:
    return SessionDetail.model_validate(service.cancel(session_id, request.state.principal.id))
