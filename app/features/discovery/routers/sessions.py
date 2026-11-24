from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import provide_optional_user_id
from app.api.schemas import ErrorResponse
from app.domain.enums import rank_to_skill, skill_to_rank
from app.features.discovery.contracts import SessionFilter, SessionRecord
from app.features.discovery.schemas import PageResult, SessionQuery, SessionSummary
from app.features.discovery.service import DiscoveryService


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


def to_session_response(record: SessionRecord) -> SessionSummary:
    values = asdict(record)
    # Repository giữ rank số; chỉ đổi sang mã trình ở biên API.
    values["host"]["skill_level"] = rank_to_skill(values["host"]["skill_level"])
    for field in ("min_level", "max_level"):
        values[field] = rank_to_skill(values[field])
    return SessionSummary.model_validate(values)


def create_sessions_router(provide_service: Callable[..., DiscoveryService]) -> APIRouter:
    router = APIRouter(tags=["Discovery"])

    @router.get(
        "/sessions",
        response_model=PageResult[SessionSummary],
        summary="Tìm kèo (host_me=true cần JWT)",
        responses={
            401: {"model": ErrorResponse, "description": "UNAUTHORIZED: thiếu hoặc sai token"},
            422: {
                "model": ErrorResponse,
                "description": "VALIDATION_ERROR hoặc INVALID_TIME_WINDOW",
            },
            503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
        },
        openapi_extra={"security": [{}, {"HTTPBearer": []}]},
    )
    def list_sessions(
        query: Annotated[SessionQuery, Query()],
        viewer_id: int | None = Depends(provide_optional_user_id),
        service: DiscoveryService = Depends(provide_service),
    ) -> PageResult[SessionSummary]:
        # host_me thiếu token: middleware trả 401 trước, service kiểm lại.
        session_filter = to_session_filter(query, viewer_id)
        page = service.search_sessions(session_filter, viewer_id)
        return PageResult[SessionSummary](
            items=[to_session_response(item) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
        )

    return router
