from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPBearer

from app.api.schemas import ErrorResponse
from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.sessions.session_repository import SqlAlchemySessionRepository
from app.features.sessions.session_schemas import CreateSessionRequest
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
) -> dict[str, int]:
    session_id = service.create(
        data=payload.to_input(),
        host_id=request.state.principal.id,
    )
    return {"id": session_id}
