import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import UserModel
from app.features.auth import dependencies
from app.features.auth.security import Argon2PasswordHasher
from app.main import app


def test_registration_with_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: sessionmaker[Session],
) -> None:
    # Cho dependency thật sử dụng SQLite tạm của test.
    monkeypatch.setattr(
        dependencies,
        "_session_factory",
        db_session_factory,
    )

    payload = {
        "email": " Player01@Example.com ",
        "password": "example-password",
        "display_name": " Player 01 ",
        "skill_level": "TB",
        "gender": "MALE",
    }

    with TestClient(app) as client:
        # Đăng ký thành công.
        first = client.post("/auth/register", json=payload)

        assert first.status_code == 201
        user_id = first.json()["id"]
        timestamp = first.json()["created_at"]
        assert timestamp.endswith("Z") and first.json()["updated_at"] == timestamp
        assert first.json() == {
            "id": user_id,
            "email": "player01@example.com",
            "display_name": "Player 01",
            "skill_level": "TB",
            "gender": "MALE",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        # Email đã tồn tại.
        duplicate = client.post(
            "/auth/register",
            json=payload | {"email": "player01@example.com"},
        )

        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

        # Tên không hợp lệ.
        invalid = client.post(
            "/auth/register",
            json=payload
            | {
                "email": "invalid@example.com",
                "display_name": "   ",
            },
        )

        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

        # Sau các request lỗi, ứng dụng vẫn đăng ký được user mới.
        second = client.post(
            "/auth/register",
            json=payload | {"email": "player02@example.com"},
        )

        assert second.status_code == 201
        assert second.json()["id"] != user_id

    # Mở session mới để xác nhận dữ liệu đã được commit.
    with db_session_factory() as session:
        users = session.scalars(select(UserModel).order_by(UserModel.id)).all()

        assert [user.email for user in users] == [
            "player01@example.com",
            "player02@example.com",
        ]
        assert users[0].id == user_id
        assert users[0].skill_level == 9
        assert users[0].gender == "MALE"
        assert users[0].created_at.isoformat().replace("+00:00", "Z") == timestamp

        hasher = Argon2PasswordHasher()
        for user in users:
            assert user.password_hash != payload["password"]
            assert hasher.verify(payload["password"], user.password_hash)
