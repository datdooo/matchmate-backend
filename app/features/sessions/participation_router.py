from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from fastapi.security import HTTPBearer

from app.api.schemas import ErrorResponse
from app.features.sessions.participation_dependencies import provide_participation_service
from app.features.sessions.participation_schemas import (
    DecisionRequest,
    JoinSessionRequest,
    ParticipationDetailResponse,
)
from app.features.sessions.participation_service import ParticipationService

router = APIRouter(tags=["Participations"], dependencies=[Depends(HTTPBearer(auto_error=False))])
Service = Annotated[ParticipationService, Depends(provide_participation_service)]
ParticipationId = Annotated[int, Path(gt=0, le=9223372036854775807)]
errors = {code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 500, 503)}


@router.post(
    "/participations", status_code=201, response_model=ParticipationDetailResponse, responses=errors
)
def join(
    payload: JoinSessionRequest, request: Request, service: Service
) -> ParticipationDetailResponse:
    return ParticipationDetailResponse.from_detail(
        service.join(request.state.principal.id, payload.session_id)
    )


@router.post(
    "/participations/{participation_id}/decision",
    response_model=ParticipationDetailResponse,
    responses=errors,
)
def decide(
    participation_id: ParticipationId, payload: DecisionRequest, request: Request, service: Service
) -> ParticipationDetailResponse:
    return ParticipationDetailResponse.from_detail(
        service.decide(request.state.principal.id, participation_id, payload.decision)
    )


@router.delete(
    "/participations/{participation_id}",
    response_model=ParticipationDetailResponse,
    responses=errors,
)
def withdraw(
    participation_id: ParticipationId, request: Request, service: Service
) -> ParticipationDetailResponse:
    return ParticipationDetailResponse.from_detail(
        service.withdraw(request.state.principal.id, participation_id)
    )
