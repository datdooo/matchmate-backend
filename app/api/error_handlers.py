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


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmailAlreadyExistsError)
    async def handle_email_already_exists(
        request: Request,
        exc: EmailAlreadyExistsError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        if request_id is None:
            request_id = uuid4().hex

        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "EMAIL_ALREADY_EXISTS",
                    "message": "Email da duoc dang ky",
                    "details": {},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        if request_id is None:
            request_id = uuid4().hex

        errors = [
            {
                "location": list(error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Du lieu dau vao khong hop le",
                    "details": {"errors": errors},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(DatabaseBusyError)
    async def handle_database_busy(
        request: Request,
        exc: DatabaseBusyError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        if request_id is None:
            request_id = uuid4().hex

        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "1"},
            content={
                "error": {
                    "code": "DATABASE_BUSY",
                    "message": "Hệ thống đang bận, vui lòng thử lại",
                    "details": {},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(InvalidCredentialsError)
    async def handle_invalid_credentials(
        request: Request,
        exc: InvalidCredentialsError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid4().hex

        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            content={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Email hoặc mật khẩu không đúng",
                    "details": {},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(SessionError)
    async def handle_session_error(
        request: Request,
        exc: SessionError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid4().hex

        status_codes = {
            "TIME_CONFLICT": 409,
            "VENUE_NOT_FOUND": 404,
            "VENUE_INACTIVE": 409,
            "UNAUTHORIZED": 401,
            "PROFILE_INCOMPLETE": 409,
            "VALIDATION_ERROR": 422,
        }
        status_code = status_codes.get(exc.code, 400)

        return JSONResponse(
            status_code=status_code,
            headers={"X-Request-ID": request_id},
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": {},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(DomainError)
    async def handle_domain_error(
        request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or uuid4().hex

        status_codes = {
            "TIME_CONFLICT": 409,
            "VENUE_NOT_FOUND": 404,
            "VENUE_INACTIVE": 409,
            "UNAUTHORIZED": 401,
            "PROFILE_INCOMPLETE": 409,
            "VALIDATION_ERROR": 422,
            "INVALID_TIME_WINDOW": 422,
            "ELIGIBILITY_MISMATCH": 409,
            "FORBIDDEN": 403,
            "SESSION_NOT_FOUND": 404,
            "PARTICIPATION_NOT_FOUND": 404,
            "SESSION_CANCELLED": 409,
            "SESSION_ALREADY_STARTED": 409,
            "SESSION_FULL": 409,
            "PARTICIPATION_ALREADY_EXISTS": 409,
            "INVALID_STATE": 409,
            "HOST_PARTICIPATION_REQUIRED": 409,
        }
        status_code = status_codes.get(exc.code, 500)

        return JSONResponse(
            status_code=status_code,
            headers={
                "X-Request-ID": request_id,
                **({"WWW-Authenticate": "Bearer"} if status_code == 401 else {}),
            },
            content={
                "error": {
                    "code": exc.code if status_code != 500 else "INTERNAL_ERROR",
                    "message": exc.message if status_code != 500 else "Không thể xử lý yêu cầu",
                    "details": exc.details if status_code != 500 else {},
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_internal_error(request: Request, exc: Exception) -> JSONResponse:
        # Giữ SQL/params/exception gốc ở phía server, không đưa vào response.
        return make_error_response(
            request, status_code=500, code="INTERNAL_ERROR", message="Không thể xử lý yêu cầu"
        )


def make_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or uuid4().hex

    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": request_id, **(headers or {})},
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "request_id": request_id,
            }
        },
    )
