"""Smoke checks for the actual skeleton, not planned business endpoints."""

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


def test_openapi_has_health_and_registration() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {"/health", "/auth/register"}
    assert "get" in schema["paths"]["/health"]
    assert "post" in schema["paths"]["/auth/register"]
