import pytest
from pydantic import ValidationError

from app.features.auth.schemas import RegisterRequest


def valid_register_data() -> dict[str, str]:
    return {
        "email": "player01@example.com",
        "password": "example-password",
        "display_name": "Player 01",
        "skill_level": "TB",
        "gender": "MALE",
    }


def test_register_normalizes_email_and_name() -> None:
    data = valid_register_data()
    data["email"] = " PLAYER01@EXAMPLE.COM "
    data["display_name"] = " Player 01 "
    data["password"] = " example-password "

    request = RegisterRequest(**data)

    assert str(request.email) == "player01@example.com"
    assert request.display_name == "Player 01"
    assert request.password == " example-password "


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", "   "),
        ("display_name", "A" * 81),
        ("password", "short"),
        ("password", "A" * 129),
        ("email", "invalid-email"),
        ("skill_level", "TB++"),
        ("gender", "UNSPECIFIED"),
    ],
)
def test_register_rejects_invalid_input(field: str, value: str) -> None:
    data = valid_register_data()
    data[field] = value
    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(**data)

    assert any(error["loc"] == (field,) for error in exc_info.value.errors())


def test_register_rejects_extra_fields() -> None:
    data = valid_register_data()
    data["user_id"] = "123"

    with pytest.raises(ValidationError) as exc_info:
        RegisterRequest(**data)

    assert any(
        error["loc"] == ("user_id",) and error["type"] == "extra_forbidden"
        for error in exc_info.value.errors()
    )
