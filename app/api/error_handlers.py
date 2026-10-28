"""Một chỗ tạo envelope lỗi; middleware và các feature dùng chung."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError
from app.features.auth.contracts import (
    DatabaseBusyError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
)
from app.features.sessions.session_contracts import SessionError

_HTTP_STATUS = {
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "VENUE_NOT_FOUND": 404,
    "SESSION_NOT_FOUND": 404,
    "PARTICIPATION_NOT_FOUND": 404,
    "TIME_CONFLICT": 409,
    "VENUE_INACTIVE": 409,
    "PROFILE_INCOMPLETE": 409,
    "ELIGIBILITY_MISMATCH": 409,
    "SESSION_CANCELLED": 409,
    "SESSION_ALREADY_STARTED": 409,
    "SESSION_FULL": 409,
    "PARTICIPATION_ALREADY_EXISTS": 409,
    "INVALID_STATE": 409,
    "HOST_PARTICIPATION_REQUIRED": 409,
    "VALIDATION_ERROR": 422,
    "INVALID_TIME_WINDOW": 422,
}


def make_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or uuid4().hex
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": request_id, **(headers or {})},
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmailAlreadyExistsError)
    async def duplicate_email(request: Request, exc: EmailAlreadyExistsError) -> JSONResponse:
        return make_error_response(
            request, status_code=409, code="EMAIL_ALREADY_EXISTS", message="Email đã được đăng ký"
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_login(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return make_error_response(
            request,
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(DatabaseBusyError)
    async def database_busy(request: Request, exc: DatabaseBusyError) -> JSONResponse:
        return make_error_response(
            request,
            status_code=503,
            code="DATABASE_BUSY",
            message="Hệ thống đang bận, vui lòng thử lại",
            headers={"Retry-After": "1"},
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Không đưa input gốc vào details: body có thể chứa password hoặc token.
        errors = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return make_error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Dữ liệu đầu vào không hợp lệ",
            details={"errors": errors},
        )

    @app.exception_handler(SessionError)
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError | SessionError) -> JSONResponse:
        status_code = _HTTP_STATUS.get(exc.code, 500)
        if status_code == 500:
            return await internal_error(request, exc)
        return make_error_response(
            request,
            status_code=status_code,
            code=exc.code,
            message=exc.message,
            details=getattr(exc, "details", {}),
            headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None,
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        # Lỗi kỹ thuật giữ ở server; không gửi SQL/params/exception gốc ra client.
        return make_error_response(
            request, status_code=500, code="INTERNAL_ERROR", message="Không thể xử lý yêu cầu"
        )
