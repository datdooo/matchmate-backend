"""Runner một máy, một worker, DB tạm mới cho từng lượt read/lifecycle."""

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REQUIRED_ROUTES = {
    ("post", "/auth/register"),
    ("post", "/auth/login"),
    ("get", "/venues"),
    ("get", "/sessions"),
    ("post", "/sessions"),
    ("get", "/sessions/{session_id}"),
    ("delete", "/sessions/{session_id}"),
    ("post", "/participations"),
    ("post", "/participations/{participation_id}/decision"),
    ("delete", "/participations/{participation_id}"),
    ("post", "/matching/requests"),
}
SPAWN_RATES = {10: 2, 50: 5, 100: 10}


def missing_routes(schema):
    paths = schema["paths"]
    return sorted(
        (method, path) for method, path in REQUIRED_ROUTES if method not in paths.get(path, {})
    )


def prepare_dataset(engine, users, now):
    from sqlalchemy import select

    from app.db.base import Base
    from app.db.models import SessionModel, UserModel
    from app.db.session import create_session_factory
    from scripts.seed import seed_venue
    from scripts.seed_load_data import (
        TEST_PASSWORD,
        build_session_specs,
        build_user_specs,
        create_sessions,
        get_venues,
        make_users,
    )

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        seed_venue(db)
        db.flush()
        venues = get_venues(db)
        specs = build_user_specs(extra_users=max(10, users - 30))
        readers = make_users(db, specs, now)
        session_specs = build_session_specs(specs, now)
        create_sessions(db, session_specs, venues, readers, now)
        pairs = []
        for index in range(users):
            credentials = {}
            for role, gender in (("host", "MALE"), ("player", "FEMALE")):
                email = f"lifecycle_{index}_{role}@example.com"
                db.add(
                    UserModel(
                        email=email,
                        display_name=f"Load {index} {role}",
                        password_hash=readers[0].password_hash,
                        skill_level=9,
                        gender=gender,
                        created_at=now,
                        updated_at=now,
                    )
                )
                credentials[role] = {"email": email, "password": TEST_PASSWORD}
            pairs.append(credentials)
        db.commit()
        return {
            "read": [{"email": user.email, "password": TEST_PASSWORD} for user in readers[:users]],
            "pairs": pairs,
            "venue_ids": [venue.id for venue in venues],
            "district_codes": [venue.district_code for venue in venues],
            "session_ids": list(db.scalars(select(SessionModel.id).order_by(SessionModel.id))),
            "base_time": now.isoformat(),
            "seed_hash": hashlib.sha256(
                json.dumps(
                    {"users": specs, "sessions": session_specs}, default=str, sort_keys=True
                ).encode()
            ).hexdigest(),
        }


def check_invariants(engine):
    statements = {
        "over_capacity": """SELECT COUNT(*) FROM (
            SELECT s.id FROM sessions s JOIN participations p ON p.session_id=s.id
            WHERE p.status='ACCEPTED' GROUP BY s.id,s.play_type
            HAVING COUNT(*) > CASE s.play_type WHEN 'SINGLES' THEN 2 ELSE 4 END)""",
        "accepted_overlap": """SELECT COUNT(*) FROM participations p
            JOIN participations q ON p.user_id=q.user_id AND p.id<q.id
            JOIN sessions s ON s.id=p.session_id JOIN sessions t ON t.id=q.session_id
            WHERE p.status='ACCEPTED' AND q.status='ACCEPTED'
            AND s.starts_at<t.ends_at AND t.starts_at<s.ends_at""",
        "active_in_cancelled": """SELECT COUNT(*) FROM sessions s
            JOIN participations p ON p.session_id=s.id WHERE s.status='CANCELLED'
            AND p.status IN ('PENDING','ACCEPTED')""",
    }
    with engine.connect() as connection:
        return {
            key: connection.exec_driver_sql(sql).scalar_one() for key, sql in statements.items()
        }


def run_case(profile, users, output, seed):
    from app.db.session import create_db_engine

    prefix = output / f"locust-{profile}-{users}u"
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="matchmate-load-") as temporary:
        temporary = Path(temporary)
        database_url = f"sqlite:///{temporary / 'load.db'}"
        engine = create_db_engine(database_url)
        manifest = prepare_dataset(engine, users, now)
        encoded = json.dumps(manifest, sort_keys=True)
        manifest_path = temporary / "actors.json"
        manifest_path.write_text(encoded)
        manifest_path.chmod(0o600)
        timing_path = temporary / "timing.json"
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        env = os.environ | {
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": secrets.token_urlsafe(48),
            "MM_LOAD_MANIFEST": str(manifest_path),
            "MM_LOAD_TIMING": str(timing_path),
            "MM_LOAD_USERS": str(users),
            "MM_LOAD_SEED": str(seed),
        }
        with prefix.with_suffix(".log").open("w") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--workers",
                    "1",
                    "--no-access-log",
                ],
                env=env,
                stdout=log,
                stderr=log,
            )
            exit_code = 124
            try:
                deadline = time.monotonic() + 15
                while True:
                    try:
                        with urlopen(base_url + "/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError):
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError(
                                f"Server không khởi động; xem {prefix}.log"
                            ) from None
                        time.sleep(0.1)
                workload = f"tests/load/locust_{profile}.py"
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "locust",
                        "-f",
                        workload,
                        "--headless",
                        "--host",
                        base_url,
                        "--users",
                        str(users),
                        "--spawn-rate",
                        str(SPAWN_RATES[users]),
                        "--html",
                        f"{prefix}-report.html",
                        "--csv",
                        str(prefix),
                        "ReadUser" if profile == "read" else "LifecycleUser",
                    ],
                    env=env,
                    stdout=log,
                    stderr=log,
                    timeout=220,
                )
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                pass  # metadata giữ exit_code=124 và không công nhận cửa sổ đo chưa hoàn tất
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
                engine.dispose()
        metadata = (
            json.loads(timing_path.read_text())
            if timing_path.exists()
            else {
                "measurement_complete": False,
                "errors": {},
            }
        )
        metadata.update(
            profile=profile,
            virtual_users=users,
            actor_accounts=users * (2 if profile == "lifecycle" else 1),
            spawn_rate=SPAWN_RATES[users],
            workers=1,
            exit_code=exit_code,
            sqlite_busy_timeout_ms=int(env.get("SQLITE_BUSY_TIMEOUT_MS", "5000")),
            commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            python=sys.version,
            sqlite=sqlite3.sqlite_version,
            cpu_count=os.cpu_count(),
            environment="kaggle" if Path("/kaggle/working").exists() else "local",
            resource_limits={
                name: Path(path).read_text().strip() if Path(path).exists() else None
                for name, path in {
                    "cpu_max": "/sys/fs/cgroup/cpu.max",
                    "memory_max": "/sys/fs/cgroup/memory.max",
                }.items()
            },
            dependencies={
                name: importlib.metadata.version(name)
                for name in ("fastapi", "SQLAlchemy", "locust", "uvicorn", "pydantic", "PyJWT")
            },
            dataset_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
            base_time=manifest["base_time"],
            random_seed=seed,
            invariants=check_invariants(engine),
        )
        engine.dispose()
        stats = Path(f"{prefix}_stats.csv")
        metadata["aggregate"] = {}
        if stats.exists() and metadata["measurement_complete"]:
            with stats.open() as stream:
                metadata["aggregate"] = next(
                    (row for row in csv.DictReader(stream) if row["Name"] == "Aggregated"), {}
                )
        Path(f"{prefix}-metadata.json").write_text(json.dumps(metadata, indent=2))
        return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("full", "read", "lifecycle"), default="full")
    parser.add_argument(
        "--users", type=int, nargs="+", choices=(10, 50, 100), default=[10, 50, 100]
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    from app.main import app

    missing = missing_routes(app.openapi())
    if missing:
        print(
            "Chưa chạy tải nghiệp vụ; còn thiếu: "
            + ", ".join(f"{m.upper()} {p}" for m, p in missing)
        )
        return 2
    if importlib.util.find_spec("locust") is None:
        print("Cần cài: python -m pip install -r requirements-load.txt")
        return 2
    output = Path("artifacts").resolve()
    output.mkdir(exist_ok=True)
    profiles = ("read", "lifecycle") if args.profile == "full" else (args.profile,)
    results = []
    for profile in profiles:
        for users in args.users:
            print(f"Chạy {profile}: {users} virtual users", flush=True)
            results.append(run_case(profile, users, output, args.seed))
    rows = [
        "# Kết quả tải",
        "",
        "Số đo lấy từ artifacts của từng lượt; latency tính bằng ms.",
        "Nghiệm thu Kaggle CPU dùng các lượt environment=kaggle trong metadata.",
        "",
        "| Profile | Users | Đủ 60s | RPS | p50 | p95 | p99 | 5xx | BUSY | 409 | Invariant |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        stats, errors = item["aggregate"], item["errors"]
        rows.append(
            f"| {item['profile']} | {item['virtual_users']} | {item['measurement_complete']} | "
            f"{stats.get('Requests/s', 'n/a')} | {stats.get('50%', 'n/a')} | "
            f"{stats.get('95%', 'n/a')} | {stats.get('99%', 'n/a')} | {errors.get('5xx', 0)} | "
            f"{errors.get('DATABASE_BUSY', 0)} | {errors.get('409', 0)} | {item['invariants']} |"
        )
    Path("docs/LOAD_TEST_RESULTS.md").write_text("\n".join(rows) + "\n")
    return int(
        any(
            not item["measurement_complete"]
            or item["exit_code"]
            or any(item["invariants"].values())
            for item in results
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
