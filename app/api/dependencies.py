from fastapi import Request

from app.domain.errors import DomainError


def provide_optional_user_id(request: Request) -> int | None:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return None

    return principal.id


def provide_current_user_id(request: Request) -> int:
    user_id = provide_optional_user_id(request)
    if user_id is None:
        raise DomainError("UNAUTHORIZED", "Cần đăng nhập")

    return user_id
