from collections.abc import Callable

from fastapi import APIRouter, Depends, status

from app.features.auth.schemas import RegisterRequest, UserSelf
from app.features.auth.service import AuthService


def create_auth_router(
    service_provider: Callable[..., AuthService],
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.post(
        "/register",
        response_model=UserSelf,
        status_code=status.HTTP_201_CREATED,
    )
    def register(
        payload: RegisterRequest,
        service: AuthService = Depends(service_provider),
    ) -> UserSelf:
        user = service.register(
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
            skill_level=payload.skill_level,
            gender=payload.gender,
        )

        return UserSelf(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            skill_level=user.skill_level,
            gender=user.gender,
        )

    return router
