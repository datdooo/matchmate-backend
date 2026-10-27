from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.features.auth.contracts import EmailAlreadyExistsError


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
