"""HTTP dependencies for the participation router.

Authentication itself stays in Chiến's centralized middleware. This module only consumes the
principal already attached to request.state and the service wired by the composition root.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.features.sessions.participation_service import ParticipationService


def get_participation_service(request: Request) -> ParticipationService:
    service = getattr(request.app.state, "participation_service", None)
    if not isinstance(service, ParticipationService):
        raise RuntimeError("participation_service has not been wired by the composition root")
    return service


def get_actor_user_id(request: Request) -> int:
    principal = getattr(request.state, "principal", None)
    user_id: object | None = None
    if isinstance(principal, int):
        user_id = principal
    elif isinstance(principal, dict):
        user_id = principal.get("user_id", principal.get("sub"))
    elif principal is not None:
        user_id = getattr(principal, "user_id", getattr(principal, "sub", None))

    if isinstance(user_id, str) and user_id.isdecimal():
        user_id = int(user_id)
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UNAUTHORIZED",
        )
    return user_id
