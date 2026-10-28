"""Kiểm workload bằng response giả; cần requirements-load, không tạo số đo tải."""

import random
from pathlib import Path

import pytest


class FakeResponse:
    def __init__(self, data, status, errors):
        self.data, self.status_code, self.errors = data, status, errors

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def json(self):
        return self.data

    def failure(self, message):
        self.errors.append(message)


class FakeClient:
    def __init__(self, responses):
        self.responses, self.calls, self.errors = responses, [], []

    def request(self, method, path, **kwargs):
        data = self.responses[len(self.calls)]
        self.calls.append((method, path, kwargs))
        status = 201 if method == "POST" and path in ("/sessions", "/participations") else 200
        return FakeResponse(data, status, self.errors)


@pytest.fixture
def workload(monkeypatch):
    # Test chỉ gọi task trực tiếp, không để Locust patch socket/thread của bộ test API.
    monkeypatch.setenv("LOCUST_SKIP_MONKEY_PATCH", "1")
    pytest.importorskip("locust", reason="Cài requirements-load.txt để kiểm workload")
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    from locust.env import Environment
    from locust_lifecycle import LifecycleUser

    monkeypatch.setattr(LifecycleUser, "host", "http://127.0.0.1")

    def make(cancel_session=False):
        game = {
            "id": 10,
            "status": "OPEN",
            "accepted_count": 1,
            "host": {},
            "venue": {},
            "my_participations": [],
            "management": None,
        }
        part = {
            "id": 20,
            "session_id": 10,
            "status": "PENDING",
            "gender_at_join": "FEMALE",
            "quoted_fee_vnd": 40000,
            "session": {"id": 10},
        }
        responses = [
            game,
            part,
            {**part, "status": "ACCEPTED"},
            {**game, "accepted_count": 2},
            {**game, "status": "CANCELLED", "accepted_count": 0}
            if cancel_session
            else {**part, "status": "CANCELLED"},
        ]
        user = LifecycleUser(Environment())
        user.client = FakeClient(responses)
        user.rng = random.Random(42)
        user.rng.random = lambda: 0.75 if cancel_session else 0.25
        user.round = 0
        user.manifest = {"base_time": "2030-11-01T00:00:00+00:00", "venue_ids": [1]}
        user.headers, user.player_headers = {"Actor": "host"}, {"Actor": "player"}
        return user

    return make


@pytest.mark.parametrize("cancel_session", [False, True])
def test_lifecycle_uses_separate_actors_and_new_schedule(workload, cancel_session):
    user = workload(cancel_session)
    user.lifecycle_round()
    assert not user.client.errors
    assert [call[2]["headers"]["Actor"] for call in user.client.calls] == [
        "host",
        "player",
        "host",
        "player",
        "host" if cancel_session else "player",
    ]
    target = "/sessions/10" if cancel_session else "/participations/20"
    assert user.client.calls[-1][:2] == ("DELETE", target)
    first_start = user.client.calls[0][2]["json"]["starts_at"]
    user.client.calls.clear()
    user.lifecycle_round()
    assert not user.client.errors
    assert user.client.calls[0][2]["json"]["starts_at"] != first_start


@pytest.mark.parametrize(
    "step,changed,cancel_session",
    [
        (0, {"accepted_count": 0}, False),
        (1, {"status": "ACCEPTED"}, False),
        (1, {"session_id": 99}, False),
        (2, {"status": "PENDING"}, False),
        (2, {"quoted_fee_vnd": 0}, False),
        (3, {"accepted_count": 1}, False),
        (4, {"status": "ACCEPTED"}, False),
        (4, {"accepted_count": 1}, True),
    ],
)
def test_lifecycle_rejects_wrong_state_even_with_success_http(
    workload, step, changed, cancel_session
):
    user = workload(cancel_session)
    user.client.responses[step].update(changed)
    user.lifecycle_round()
    assert user.client.errors == ["Response sai giá trị theo contract"]
    assert len(user.client.calls) == step + 1


def test_lifecycle_stops_when_create_returns_only_id(workload):
    user = workload()
    user.client.responses[0] = {"id": 10}
    user.lifecycle_round()
    assert user.client.errors == ["Response thiếu field theo contract"]
    assert len(user.client.calls) == 1
