"""Smoke test cho app thật; mỗi feature kiểm contract route của mình."""

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documentation_available() -> None:
    with TestClient(app) as client:
        for path in ("/docs", "/redoc"):
            response = client.get(path)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]


def test_openapi_includes_implemented_routes() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    # Feature mới được thêm route mà không làm hỏng smoke test nền tảng.
    assert {"/health", "/auth/register", "/auth/login", "/sessions"} <= set(schema["paths"])
    assert "get" in schema["paths"]["/health"]
    assert "post" in schema["paths"]["/auth/register"]
