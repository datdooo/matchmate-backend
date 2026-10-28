from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, status

from app.api.schemas import ErrorResponse
from app.features.auth.contracts import TokenIssuer
from app.features.auth.schemas import LoginRequest, RegisterRequest, TokenData, UserSelf
from app.features.auth.service import AuthService


def create_auth_router(
    service_provider: Callable[..., AuthService | Iterator[AuthService]],
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.post(
        "/register",
        response_model=UserSelf,
        status_code=status.HTTP_201_CREATED,
        responses={
            409: {
                "model": ErrorResponse,
                "description": "EMAIL_ALREADY_EXISTS: email đã được đăng ký",
            },
            422: {
                "model": ErrorResponse,
                "description": "VALIDATION_ERROR: dữ liệu không hợp lệ",
            },
            503: {
                "model": ErrorResponse,
                "description": "DATABASE_BUSY: hết thời gian chờ khóa DB",
                "headers": {
                    "Retry-After": {
                        "description": "Thời gian chờ gợi ý, tính bằng giây",
                        "schema": {"type": "integer", "example": 1},
                    }
                },
            },
        },
    )
    def register(
        payload: RegisterRequest,
        service: AuthService = Depends(service_provider, scope="function"),
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
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    return router


def create_login_router(
    service_provider: Callable[..., AuthService | Iterator[AuthService]],
    token_issuer_provider: Callable[..., TokenIssuer],
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Auth"])

    @router.post(
        "/login",
        response_model=TokenData,
        responses={
            401: {"model": ErrorResponse, "description": "INVALID_CREDENTIALS"},
            422: {"model": ErrorResponse, "description": "VALIDATION_ERROR"},
            503: {"model": ErrorResponse, "description": "DATABASE_BUSY"},
        },
    )
    def login(
        payload: LoginRequest,
        service: AuthService = Depends(service_provider, scope="function"),
        token_issuer: TokenIssuer = Depends(token_issuer_provider),
    ) -> TokenData:
        result = service.login(
            email=str(payload.email),
            password=payload.password,
            token_issuer=token_issuer,
        )
        return TokenData(
            access_token=result.access_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )

    return router
