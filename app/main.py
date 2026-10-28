"""Application entry point for MatchMate."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.features.auth.dependencies import (
    provide_login_service,
    provide_registration_service,
    provide_token_issuer,
)
from app.features.auth.middleware import JwtMiddleware
from app.features.auth.router import create_auth_router, create_login_router
from app.features.sessions.session_router import router as session_router

app = FastAPI(
    title="MatchMate",
    version="0.0.1",
    description="MatchMate Phase 1 backend.",
)
app.add_middleware(JwtMiddleware)

register_error_handlers(app)

app.include_router(create_auth_router(provide_registration_service))
app.include_router(
    create_login_router(
        provide_login_service,
        provide_token_issuer,
    )
)
app.include_router(session_router)


@app.get("/health", tags=["Technical"], summary="Application liveness")
def health() -> dict[str, str]:
    return {"status": "ok"}
