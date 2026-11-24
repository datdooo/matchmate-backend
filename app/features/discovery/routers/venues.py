from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.schemas import ErrorResponse
from app.features.discovery.contracts import VenueFilter
from app.features.discovery.schemas import PageResult, VenueQuery, VenueView
from app.features.discovery.service import DiscoveryService


def create_venues_router(provide_service: Callable[..., DiscoveryService]) -> APIRouter:
    router = APIRouter(tags=["Discovery"])

    @router.get(
        "/venues",
        response_model=PageResult[VenueView],
        summary="Tìm sân",
        responses={
            422: {
                "model": ErrorResponse,
                "description": "VALIDATION_ERROR hoặc INVALID_TIME_WINDOW",
            },
            503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
        },
    )
    def list_venues(
        query: Annotated[VenueQuery, Query()],
        service: DiscoveryService = Depends(provide_service),
    ) -> PageResult[VenueView]:
        venue_filter = VenueFilter(
            district_code=query.district_code,
            limit=query.limit,
            offset=query.offset,
        )
        page = service.search_venues(venue_filter)
        return PageResult[VenueView].model_validate(page)

    return router
