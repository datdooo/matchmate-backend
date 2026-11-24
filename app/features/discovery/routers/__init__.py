"""Assemble Discovery's venue and session search routes."""

from collections.abc import Callable

from fastapi import APIRouter

from app.features.discovery.routers.sessions import create_sessions_router
from app.features.discovery.routers.venues import create_venues_router
from app.features.discovery.service import DiscoveryService


def create_discovery_router(provide_service: Callable[..., DiscoveryService]) -> APIRouter:
    router = APIRouter()
    router.include_router(create_venues_router(provide_service))
    router.include_router(create_sessions_router(provide_service))
    return router
