"""Đăng nhập/barrier dùng chung và profile read theo quận, không dùng GPS."""

import json
import os
import random
from collections import Counter
from itertools import count
from pathlib import Path

import gevent
from gevent.event import Event
from locust import HttpUser, between, events, task
from locust.exception import StopUser


@events.test_start.add_listener
def start_measurement(environment, **_kwargs):
    random.seed(int(os.environ["MM_LOAD_SEED"]))
    manifest = json.loads(Path(os.environ["MM_LOAD_MANIFEST"]).read_text())
    state = dict(
        manifest=manifest,
        index=count(),
        ready=0,
        all_ready=Event(),
        release=Event(),
        errors=Counter(),
        measuring=False,
        measurement_complete=False,
    )
    environment.matchmate = state

    def measure():
        # Không tính login hoặc warm-up vào cửa sổ đo.
        if not state["all_ready"].wait(timeout=120):
            environment.process_exit_code = 1
            environment.runner.quit()
            return
        state["release"].set()
        gevent.sleep(15)
        if environment.stats.total.num_failures:
            environment.process_exit_code = 1
            environment.runner.quit()
            return
        environment.stats.reset_all()
        state["errors"].clear()
        state["measuring"] = True
        gevent.sleep(60)
        state["measuring"] = False
        state["measurement_complete"] = True
        environment.runner.quit()

    gevent.spawn(measure)


@events.request.add_listener
def count_errors(response=None, exception=None, **_kwargs):
    # Chỉ đếm lỗi trong cửa sổ đo; không ghi body hoặc token vào artifacts.
    state = _kwargs.get("context", {}).get("load_state")
    if state is None or not state["measuring"]:
        return
    if response is not None and response.status_code >= 400:
        status = response.status_code
        state["errors"]["5xx" if status >= 500 else "4xx"] += 1
        try:
            code = response.json().get("error", {}).get("code", f"HTTP_{status}")
        except (ValueError, AttributeError):
            code = f"HTTP_{status}"
        state["errors"][code] += 1
        if status == 409:
            state["errors"]["409"] += 1
    elif exception is not None:
        state["errors"]["request_failure"] += 1


@events.quitting.add_listener
def save_measurement(environment, **_kwargs):
    state = getattr(environment, "matchmate", None)
    if state is None:
        return
    Path(os.environ["MM_LOAD_TIMING"]).write_text(
        json.dumps(
            {
                "measurement_complete": state["measurement_complete"],
                "logged_in_users": state["ready"],
                "warmup_seconds": 15,
                "measurement_seconds": 60 if state["measurement_complete"] else 0,
                "errors": dict(state["errors"]),
            }
        )
    )


class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(1, 2)
    lifecycle = False

    def context(self):
        return {"load_state": self.environment.matchmate}

    def on_start(self):
        state = self.environment.matchmate
        self.manifest = state["manifest"]
        index = next(state["index"])
        self.rng = random.Random(int(os.environ["MM_LOAD_SEED"]) + index)
        self.round = 0
        if self.lifecycle:
            pair = self.manifest["pairs"][index]
            self.headers = self.login(pair["host"])
            self.player_headers = self.login(pair["player"])
        else:
            self.headers = self.login(self.manifest["read"][index])
        state["ready"] += 1
        if state["ready"] == int(os.environ["MM_LOAD_USERS"]):
            state["all_ready"].set()
        state["release"].wait()

    def login(self, credentials):
        data = self.request_json("POST", "/auth/login", json=credentials)
        if data is None or "access_token" not in data:
            self.environment.process_exit_code = 1
            gevent.spawn(self.environment.runner.quit)
            raise StopUser()
        return {"Authorization": f"Bearer {data['access_token']}"}

    def request_json(
        self, method, path, *, expected=200, required_fields=(), expected_values=None, **kwargs
    ):
        with self.client.request(
            method, path, catch_response=True, timeout=20, **kwargs
        ) as response:
            if response.status_code != expected:
                response.failure(f"HTTP_{response.status_code}")
                return None
            try:
                data = response.json()
            except ValueError:
                response.failure("Response không phải JSON")
                return None
            if not isinstance(data, dict) or any(field not in data for field in required_fields):
                response.failure("Response thiếu field theo contract")
                return None
            if any(data.get(field) != value for field, value in (expected_values or {}).items()):
                # HTTP đúng chưa đủ: trạng thái và snapshot cũng phải đúng sau từng bước.
                response.failure("Response sai giá trị theo contract")
                return None
            return data


class ReadUser(AuthenticatedUser):
    @task(7)
    def search_sessions(self):
        self.request_json(
            "GET",
            "/sessions",
            headers=self.headers,
            params={"district_code": self.rng.choice(self.manifest["district_codes"])},
            required_fields=("items", "total", "limit", "offset"),
        )

    @task(2)
    def detail(self):
        session_id = self.rng.choice(self.manifest["session_ids"])
        self.request_json(
            "GET",
            f"/sessions/{session_id}",
            name="/sessions/{id}",
            headers=self.headers,
            required_fields=("id", "my_participations", "management"),
        )

    @task
    def hosted_sessions(self):
        self.request_json(
            "GET",
            "/sessions",
            name="/sessions?host_me=true",
            headers=self.headers,
            params={"host_me": "true"},
            required_fields=("items", "total", "limit", "offset"),
        )
