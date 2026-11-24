from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer

from app.api.dependencies import provide_current_user_id
from app.api.schemas import ErrorResponse
from app.domain.enums import EffectiveStatus, rank_to_skill
from app.features.matching.contracts import CreateMatchingInput
from app.features.matching.contracts import MatchingResult as MatchingServiceResult
from app.features.matching.schemas import (
    CreateMatchingRequest,
    MatchingRequestSelf,
    MatchingResult,
    MatchingSuggestion,
)
from app.features.matching.service import MatchingService

_UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "UNAUTHORIZED: thiếu hoặc sai token"}}
_VALIDATION = {
    422: {"model": ErrorResponse, "description": "VALIDATION_ERROR hoặc INVALID_TIME_WINDOW"}
}
_BUSY = {503: {"model": ErrorResponse, "description": "DATABASE_BUSY"}}
_bearer = HTTPBearer(auto_error=False)


def to_matching_input(body: CreateMatchingRequest) -> CreateMatchingInput:
    return CreateMatchingInput(
        venue_id=body.venue_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        play_type=body.play_type,
        proposed_fee_male_vnd=body.proposed_fee_male_vnd,
        proposed_fee_female_vnd=body.proposed_fee_female_vnd,
        budget_max_vnd=body.budget_max_vnd,
        gender_policy=body.gender_policy,
    )


def to_matching_response(result: MatchingServiceResult) -> MatchingResult:
    request_response = MatchingRequestSelf.model_validate(
        {**asdict(result.request), "effective_status": EffectiveStatus.ACTIVE}
    )
    suggestion_response = None
    if result.suggestion is not None:
        values = asdict(result.suggestion)
        for member in values["members"]:
            member["skill_level"] = rank_to_skill(member["skill_level"])
        suggestion_response = MatchingSuggestion.model_validate(values)
    return MatchingResult(request=request_response, suggestion=suggestion_response)


def create_matching_router(provide_service: Callable[..., MatchingService]) -> APIRouter:
    router = APIRouter(tags=["Discovery"])

    @router.post(
        "/matching/requests",
        response_model=MatchingResult,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(_bearer)],
        summary="Đăng nhu cầu và nhận gợi ý nhóm",
        responses={
            **_UNAUTHORIZED,
            404: {"description": "VENUE_NOT_FOUND"},
            409: {
                "description": "VENUE_INACTIVE, TIME_CONFLICT, "
                "ELIGIBILITY_MISMATCH, PROFILE_INCOMPLETE"
            },
            **_VALIDATION,
            **_BUSY,
        },
    )
    def create_matching_request(
        payload: CreateMatchingRequest,
        actor_user_id: int = Depends(provide_current_user_id),
        service: MatchingService = Depends(provide_service),
    ) -> MatchingResult:
        data = to_matching_input(payload)
        result = service.create_matching_request(actor_user_id=actor_user_id, data=data)
        return to_matching_response(result)

    return router
