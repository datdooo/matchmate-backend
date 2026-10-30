from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPBearer

from app.api.schemas import ErrorResponse
from app.domain.enums import EffectiveStatus, rank_to_skill, skill_to_rank
from app.features.discovery.contracts import (
    CreateMatchingInput,
    SessionFilter,
    VenueFilter,
)
from app.features.discovery.dependencies import (
    provide_current_user_id,
    provide_optional_user_id,
)
from app.features.discovery.schemas import (
    CreateMatchingRequest,
    MatchingRequestSelf,
    MatchingResult,
    MatchingSuggestion,
    PageResult,
    SessionQuery,
    SessionSummary,
    VenueQuery,
    VenueView,
)
from app.features.discovery.service import DiscoveryService

_UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "UNAUTHORIZED: thiếu hoặc sai token"}}
_VALIDATION = {
    422: {
        "model": ErrorResponse,
        "description": "VALIDATION_ERROR hoặc INVALID_TIME_WINDOW",
    }
}
_BUSY = {503: {"model": ErrorResponse, "description": "DATABASE_BUSY"}}
_bearer = HTTPBearer(auto_error=False)


def to_session_filter(query: SessionQuery, viewer_id: int | None) -> SessionFilter:
    return SessionFilter(
        now=datetime.now(timezone.utc),
        district_code=query.district_code,
        venue_id=query.venue_id,
        play_type=query.play_type,
        available_from=query.available_from,
        available_to=query.available_to,
        skill_level=(skill_to_rank(query.skill_level) if query.skill_level is not None else None),
        gender=query.gender,
        max_fee_vnd=query.max_fee_vnd,
        only_available=query.only_available,
        host_me=query.host_me,
        host_user_id=viewer_id if query.host_me else None,
        limit=query.limit,
        offset=query.offset,
    )


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


def to_matching_response(result) -> MatchingResult:
    request_out = MatchingRequestSelf.model_validate(
        {**asdict(result.request), "effective_status": EffectiveStatus.ACTIVE}
    )
    suggestion_out = None
    if result.suggestion is not None:
        values = asdict(result.suggestion)
        for member in values["members"]:
            member["skill_level"] = rank_to_skill(member["skill_level"])
        suggestion_out = MatchingSuggestion.model_validate(values)
    return MatchingResult(request=request_out, suggestion=suggestion_out)


def to_session_response(record) -> SessionSummary:
    values = asdict(record)
    # Repository giữ rank số; chỉ đổi sang mã trình ở biên API.
    values["host"]["skill_level"] = rank_to_skill(values["host"]["skill_level"])
    for field in ("min_level", "max_level"):
        values[field] = rank_to_skill(values[field])
    return SessionSummary.model_validate(values)


def create_discovery_router(
    provide_service: Callable[..., DiscoveryService],
) -> APIRouter:

    router = APIRouter(tags=["Discovery"])

    @router.get(
        "/venues",
        response_model=PageResult[VenueView],
        summary="Tìm sân",
        responses={**_VALIDATION, **_BUSY},
    )
    def list_venues(
        query: Annotated[VenueQuery, Query()],
        service: DiscoveryService = Depends(provide_service),
    ) -> PageResult[VenueView]:
        filt = VenueFilter(
            district_code=query.district_code,
            limit=query.limit,
            offset=query.offset,
        )
        page = service.search_venues(filt)
        return PageResult[VenueView].model_validate(page)

    @router.get(
        "/sessions",
        response_model=PageResult[SessionSummary],
        summary="Tìm kèo (host_me=true cần JWT)",
        responses={**_UNAUTHORIZED, **_VALIDATION, **_BUSY},
        openapi_extra={"security": [{}, {"HTTPBearer": []}]},
    )
    def list_sessions(
        query: Annotated[SessionQuery, Query()],
        viewer_id: int | None = Depends(provide_optional_user_id),
        service: DiscoveryService = Depends(provide_service),
    ) -> PageResult[SessionSummary]:
        # host_me thiếu token: middleware trả 401 trước, service kiểm lại.
        filt = to_session_filter(query, viewer_id)
        page = service.search_sessions(filt, viewer_id)
        return PageResult[SessionSummary](
            items=[to_session_response(item) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

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
        body: CreateMatchingRequest,
        actor_user_id: int = Depends(provide_current_user_id),
        service: DiscoveryService = Depends(provide_service),
    ) -> MatchingResult:
        data = to_matching_input(body)
        result = service.create_matching_request(actor_user_id, data)
        return to_matching_response(result)

    return router
