"""Technical entry point only; business features are not implemented."""

from fastapi import FastAPI

app = FastAPI(
    title="MatchMate",
    version="0.0.1",
    description="Phase 1 skeleton. Only the technical health endpoint is implemented.",
)


@app.get("/health", tags=["Technical"], summary="Application liveness")
def health() -> dict[str, str]:
    """Return liveness without accessing a database or external service."""
    return {"status": "ok"}
