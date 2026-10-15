"""FastAPI routes for FR-08, FR-09 and FR-10.

The router is intentionally not included in app.main here; Chiến owns the composition root and
central route policy/error handlers. The integration PR only needs to wire app.state service and
include this router.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.features.sessions.participation_contracts import Decision
from app.features.sessions.participation_dependencies import (
    get_actor_user_id,
    get_participation_service,
)
from app.features.sessions.participation_schemas import (
    DecisionRequest,
    JoinSessionRequest,
    ParticipationDetailResponse,
)
from app.features.sessions.participation_service import ParticipationService

router = APIRouter(tags=["Participations"])
ActorUserId = Annotated[int, Depends(get_actor_user_id)]
Service = Annotated[ParticipationService, Depends(get_participation_service)]


@router.post(
    "/participations",
    response_model=ParticipationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi yêu cầu tham gia kèo",
)
def join_session(
    payload: JoinSessionRequest,
    actor_user_id: ActorUserId,
    service: Service,
) -> ParticipationDetailResponse:
    detail = service.join(actor_user_id, payload.session_id)
    return ParticipationDetailResponse.model_validate(detail)


@router.post(
    "/participations/{participation_id}/decision",
    response_model=ParticipationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Host duyệt hoặc từ chối một yêu cầu",
)
def decide_participation(
    participation_id: Annotated[int, Path(gt=0)],
    payload: DecisionRequest,
    actor_user_id: ActorUserId,
    service: Service,
) -> ParticipationDetailResponse:
    detail = service.decide(actor_user_id, participation_id, Decision(payload.decision))
    return ParticipationDetailResponse.model_validate(detail)


@router.delete(
    "/participations/{participation_id}",
    response_model=ParticipationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Rút lượt tham gia của mình",
)
def cancel_participation(
    participation_id: Annotated[int, Path(gt=0)],
    actor_user_id: ActorUserId,
    service: Service,
) -> ParticipationDetailResponse:
    detail = service.cancel(actor_user_id, participation_id)
    return ParticipationDetailResponse.model_validate(detail)
