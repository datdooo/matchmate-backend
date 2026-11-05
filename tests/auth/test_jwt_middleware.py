import os
import time

import jwt
import pytest

NOW = int(time.time())


def token(secret=None, algorithm="HS256", **claims):
    payload = {"sub": "1", "iat": NOW - 10, "exp": NOW + 3600} | claims
    payload = {key: value for key, value in payload.items() if value is not None}
    return jwt.encode(payload, secret or os.environ["JWT_SECRET_KEY"], algorithm=algorithm)


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_valid_token_is_accepted(client, auth_headers, game_data):
    response = client.get(
        f"/sessions/{game_data['first']}", headers=auth_headers(game_data["host"])
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": NOW - 5},
        {"sub": None},
        {"iat": None},
        {"exp": None},
        {"sub": "abc"},
        {"sub": "0"},
        {"sub": 1},
        {"exp": NOW - 20, "iat": NOW - 10},
        {"sub": "999999"},
    ],
    ids=[
        "expired",
        "missing_sub",
        "missing_iat",
        "missing_exp",
        "sub_not_numeric",
        "sub_zero",
        "sub_not_string",
        "exp_before_iat",
        "user_does_not_exist",
    ],
)
def test_bad_claims_are_rejected(client, game_data, claims):
    response = client.get(
        f"/sessions/{game_data['first']}", headers={"Authorization": f"Bearer {token(**claims)}"}
    )

    assert_unauthorized(response)


def test_wrong_signature_is_rejected(client, game_data):
    bad = token(secret="another-secret-that-is-at-least-32-bytes")

    response = client.get(
        f"/sessions/{game_data['first']}", headers={"Authorization": f"Bearer {bad}"}
    )

    assert_unauthorized(response)


def test_other_algorithm_is_rejected(client, game_data):
    # Cùng khóa của app, chỉ khác thuật toán, để test không bị loại vì sai chữ ký.
    bad = token(algorithm="HS512")
    response = client.get(
        f"/sessions/{game_data['first']}", headers={"Authorization": f"Bearer {bad}"}
    )

    assert_unauthorized(response)


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer a b", "abc", "Bearer not-a-jwt"])
def test_malformed_authorization_header_is_rejected(client, game_data, header):
    response = client.get(f"/sessions/{game_data['first']}", headers={"Authorization": header})

    assert_unauthorized(response)


def test_invalid_token_is_rejected_even_on_public_route(client):
    response = client.get("/venues", headers={"Authorization": "Bearer not-a-jwt"})

    assert_unauthorized(response)
