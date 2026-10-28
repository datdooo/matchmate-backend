import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.error_handlers import register_error_handlers
from app.domain.errors import DomainError
from app.features.sessions.session_contracts import SessionError


@pytest.mark.parametrize("error_type", [DomainError, SessionError])
@pytest.mark.parametrize(
    "code,status",
    [
        ("SESSION_NOT_FOUND", 404),
        ("FORBIDDEN", 403),
        ("ELIGIBILITY_MISMATCH", 409),
        ("INVALID_TIME_WINDOW", 422),
        ("UNAUTHORIZED", 401),
    ],
)
def test_both_error_types_use_the_same_contract(error_type, code, status):
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/test")
    def fail():
        raise error_type(code, "Thông báo test")

    with TestClient(app) as client:
        response = client.get("/test")
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code and error["details"] == {}
    assert error["request_id"] == response.headers["X-Request-ID"]
    if status == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unknown_error_does_not_expose_message_or_details():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/test")
    def fail():
        raise DomainError("UNMAPPED", "SQL và params nội bộ", {"private": "test"})

    with TestClient(app) as client:
        response = client.get("/test")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "SQL" not in response.text and "private" not in response.text
