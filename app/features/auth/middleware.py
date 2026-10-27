import re
from uuid import uuid4

import jwt
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.error_handlers import make_error_response
from app.config import load_settings
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.dependencies import lookup_authenticated_user


def requires_authentication(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    method = request.method

    if method == "GET" and path == "/sessions":
        host_me = request.query_params.get("host_me", "").lower()
        return host_me in {"true", "1", "yes", "on", "t", "y"}

    protected = [
        ("POST", r"/sessions"),
        ("GET", r"/sessions/[^/]+"),
        ("DELETE", r"/sessions/[^/]+"),
        ("POST", r"/participations"),
        ("POST", r"/participations/[^/]+/decision"),
        ("DELETE", r"/participations/[^/]+"),
        ("POST", r"/matching/requests"),
    ]

    return any(
        method == required_method and re.fullmatch(pattern, path)
        for required_method, pattern in protected
    )


class JwtMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = uuid4().hex
        request.state.principal = None

        def unauthorized() -> Response:
            return make_error_response(
                request,
                status_code=401,
                code="UNAUTHORIZED",
                message="Yêu cầu đăng nhập bằng token hợp lệ",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if request.method != "OPTIONS":
            authorization = request.headers.get("Authorization")

            if authorization is None:
                if requires_authentication(request):
                    return unauthorized()
            else:
                parts = authorization.split()
                if len(parts) != 2 or parts[0].lower() != "bearer":
                    return unauthorized()

                settings = load_settings()

                try:
                    claims = jwt.decode(
                        parts[1],
                        settings.jwt_secret_key,
                        algorithms=["HS256"],
                        options={"require": ["sub", "iat", "exp"]},
                    )

                    subject = claims["sub"]
                    if not isinstance(subject, str) or not re.fullmatch(
                        r"[1-9][0-9]{0,18}", subject
                    ):
                        raise jwt.InvalidTokenError()

                    user_id = int(subject)
                    if user_id > 9223372036854775807:
                        raise jwt.InvalidTokenError()

                    if (
                        type(claims["iat"]) is not int
                        or type(claims["exp"]) is not int
                        or claims["exp"] <= claims["iat"]
                    ):
                        raise jwt.InvalidTokenError()

                except jwt.InvalidTokenError:
                    return unauthorized()

                try:
                    user = await run_in_threadpool(lookup_authenticated_user, user_id)
                except DatabaseBusyError:
                    return make_error_response(
                        request,
                        status_code=503,
                        code="DATABASE_BUSY",
                        message="Hệ thống đang bận, vui lòng thử lại",
                        headers={"Retry-After": "1"},
                    )

                if user is None:
                    return unauthorized()

                request.state.principal = user

        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
