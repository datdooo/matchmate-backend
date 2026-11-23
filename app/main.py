"""Application entry point for MatchMate."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.composition import provide_discovery_service, provide_matching_service
from app.features.auth.dependencies import (
    provide_auth_service,
    provide_token_issuer,
)
from app.features.auth.middleware import JwtMiddleware
from app.features.auth.router import create_auth_router, create_login_router
from app.features.discovery.router import create_discovery_router
from app.features.matching.router import create_matching_router
from app.features.sessions.participation_router import router as participation_router
from app.features.sessions.session_router import router as session_router

app = FastAPI(
    title="MatchMate",
    version="0.0.1",
    description="MatchMate Phase 1 backend.",
)
app.add_middleware(JwtMiddleware)

register_error_handlers(app)

app.include_router(create_auth_router(provide_auth_service))
app.include_router(
    create_login_router(
        provide_auth_service,
        provide_token_issuer,
    )
)
app.include_router(create_discovery_router(provide_discovery_service))
app.include_router(create_matching_router(provide_matching_service))
app.include_router(session_router)
app.include_router(participation_router)


@app.get("/health", tags=["Technical"], summary="Application liveness")
def health() -> dict[str, str]:
    return {"status": "ok"}
