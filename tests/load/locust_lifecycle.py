from datetime import datetime, timedelta

from locust import task
from locust_read import AuthenticatedUser


class LifecycleUser(AuthenticatedUser):
    lifecycle = True

    @task
    def lifecycle_round(self):
        starts_at = datetime.fromisoformat(self.manifest["base_time"]) + timedelta(
            days=1, hours=self.round * 4
        )
        self.round += 1
        # Cặp actor riêng và lịch mới mỗi vòng để tải thường không tự tranh chỗ.
        game = self.request_json(
            "POST",
            "/sessions",
            expected=201,
            required_fields=("id", "host", "venue", "my_participations", "management"),
            headers=self.headers,
            json={
                "venue_id": self.rng.choice(self.manifest["venue_ids"]),
                "title": "Kèo load test",
                "starts_at": starts_at.isoformat(),
                "ends_at": (starts_at + timedelta(hours=2)).isoformat(),
                "play_type": "DOUBLES" if self.round % 2 else "SINGLES",
                "fee_male_vnd": 60000,
                "fee_female_vnd": 40000,
                "min_level": "NEWBIE",
                "max_level": "T_PLUS",
                "gender_policy": "ANY",
            },
        )
        if game is None:
            return
        pending = self.request_json(
            "POST",
            "/participations",
            expected=201,
            required_fields=("id", "status", "session"),
            headers=self.player_headers,
            json={"session_id": game["id"]},
        )
        if pending is None:
            return
        part_id = pending["id"]
        approved = self.request_json(
            "POST",
            f"/participations/{part_id}/decision",
            name="/participations/{id}/decision",
            required_fields=("id", "status", "session"),
            headers=self.headers,
            json={"decision": "APPROVE"},
        )
        if approved is None:
            return
        detail = self.request_json(
            "GET",
            f"/sessions/{game['id']}",
            name="/sessions/{id}",
            headers=self.player_headers,
            required_fields=("id", "my_participations", "management"),
        )
        if detail is None:
            return
        # Không wait giữa các bước; Locust chỉ wait 1–2 giây sau cả vòng.
        if self.rng.random() < 0.5:
            self.request_json(
                "DELETE",
                f"/participations/{part_id}",
                name="/participations/{id}",
                headers=self.player_headers,
                required_fields=("id", "status", "session"),
            )
        else:
            self.request_json(
                "DELETE",
                f"/sessions/{game['id']}",
                name="/sessions/{id}",
                headers=self.headers,
                required_fields=("id", "host", "venue", "my_participations", "management"),
            )
