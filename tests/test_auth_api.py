from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.error_handlers import register_error_handlers
from app.features.auth.contracts import (
    EmailAlreadyExistsError,
    NewUser,
    User,
)
from app.features.auth.router import create_auth_router
from app.features.auth.security import Argon2PasswordHasher
from app.features.auth.service import AuthService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.saved_data: NewUser | None = None

    def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    def create(self, data: NewUser) -> User:
        if data.email in self.users:
            raise EmailAlreadyExistsError()

        user = User(
            id=len(self.users) + 1,
            email=data.email,
            display_name=data.display_name,
            skill_level=data.skill_level,
            gender=data.gender,
            created_at=data.created_at,
            updated_at=data.created_at,
        )
        self.users[data.email] = user
        self.saved_data = data
        return user


def build_test_app(repository: FakeUserRepository) -> FastAPI:
    service = AuthService(repository, Argon2PasswordHasher())

    def provide_service() -> AuthService:
        return service

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(create_auth_router(provide_service))
    return app


def test_register_returns_201_without_password() -> None:
    repository = FakeUserRepository()
    app = build_test_app(repository)

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": " PLAYER01@EXAMPLE.COM",
                "password": "example-password",
                "display_name": " Player 01 ",
                "skill_level": "TB",
                "gender": "MALE",
            },
        )

    assert response.status_code == 201
    timestamp = repository.saved_data.created_at.isoformat().replace("+00:00", "Z")
    assert response.json() == {
        "id": 1,
        "email": "player01@example.com",
        "display_name": "Player 01",
        "skill_level": "TB",
        "gender": "MALE",
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    saved = repository.saved_data
    assert saved is not None
    assert Argon2PasswordHasher().verify("example-password", saved.password_hash)


def test_register_invalid_input_does_not_create_user() -> None:
    repository = FakeUserRepository()
    app = build_test_app(repository)

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "player01@example.com",
                "password": "example-password",
                "display_name": "   ",
                "skill_level": "TB",
                "gender": "MALE",
            },
        )

    assert response.status_code == 422

    error = response.json()["error"]

    assert error["code"] == "VALIDATION_ERROR"
    assert error["request_id"]
    errors = error["details"]["errors"]
    assert any(item["location"] == ["body", "display_name"] for item in errors)
    assert repository.users == {}
    assert repository.saved_data is None


def test_register_duplicate_email_returns_409() -> None:
    repository = FakeUserRepository()
    app = build_test_app(repository)

    payload = {
        "email": "player01@example.com",
        "password": "example-password",
        "display_name": "Player 01",
        "skill_level": "TB",
        "gender": "MALE",
    }

    with TestClient(app) as client:
        first_response = client.post("/auth/register", json=payload)

        payload["email"] = " PLAYER01@EXAMPLE.COM "
        second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    error = second_response.json()["error"]
    assert error["code"] == "EMAIL_ALREADY_EXISTS"
    assert error["details"] == {}
    assert isinstance(error["request_id"], str)
    assert error["request_id"]
    assert len(repository.users) == 1
