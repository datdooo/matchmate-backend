"""Application entry point for MatchMate."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.features.auth.dependencies import provide_registration_service
from app.features.auth.router import create_auth_router

app = FastAPI(
    title="MatchMate",
    version="0.0.1",
    description="MatchMate Phase 1 backend.",
)

register_error_handlers(app)
app.include_router(create_auth_router(provide_registration_service))


@app.get("/health", tags=["Technical"], summary="Application liveness")
def health() -> dict[str, str]:
    return {"status": "ok"}
