from enum import Enum

from starlette.requests import Request
from starlette.routing import compile_path


class RouteAccess(Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    HOST_ME = "authenticated when host_me is true"


ROUTE_ACCESS = {
    ("GET", "/health"): RouteAccess.PUBLIC,
    ("GET", "/venues"): RouteAccess.PUBLIC,
    ("POST", "/auth/register"): RouteAccess.PUBLIC,
    ("POST", "/auth/login"): RouteAccess.PUBLIC,
    ("GET", "/sessions"): RouteAccess.HOST_ME,
    ("POST", "/sessions"): RouteAccess.AUTHENTICATED,
    ("GET", "/sessions/{session_id}"): RouteAccess.AUTHENTICATED,
    ("DELETE", "/sessions/{session_id}"): RouteAccess.AUTHENTICATED,
    ("POST", "/participations"): RouteAccess.AUTHENTICATED,
    ("POST", "/participations/{participation_id}/decision"): RouteAccess.AUTHENTICATED,
    ("DELETE", "/participations/{participation_id}"): RouteAccess.AUTHENTICATED,
    ("POST", "/matching/requests"): RouteAccess.AUTHENTICATED,
    **{
        (method, path): RouteAccess.PUBLIC
        for method in ("GET", "HEAD")
        for path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")
    },
}

_PARAMETERIZED_ROUTES = tuple(
    (method, compile_path(path)[0], access)
    for (method, path), access in ROUTE_ACCESS.items()
    if "{" in path
)
_TRUE_QUERY_VALUES = {"true", "1", "yes", "on", "t", "y"}


def requires_authentication(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    access = ROUTE_ACCESS.get((request.method, path))
    if access is None:
        access = next(
            (
                policy
                for method, pattern, policy in _PARAMETERIZED_ROUTES
                if method == request.method and pattern.fullmatch(path)
            ),
            None,
        )

    return access is RouteAccess.AUTHENTICATED or (
        access is RouteAccess.HOST_ME
        and request.query_params.get("host_me", "").lower() in _TRUE_QUERY_VALUES
    )
