import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from app.features.auth.security import Argon2PasswordHasher
from scripts.seed_load_data import TEST_PASSWORD


def run_seed(module, directory):
    project = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "-m", module],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PYTHONPATH": str(project),
            "DATABASE_URL": f"sqlite:///{directory / 'app.db'}",
        },
    )


def test_demo_seed_is_idempotent(tmp_path):
    run_seed("scripts.seed", tmp_path)
    run_seed("scripts.seed", tmp_path)
    with closing(sqlite3.connect(tmp_path / "app.db")) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == {"users", "venues", "sessions", "participations", "matching_requests"}
        assert connection.execute("SELECT COUNT(*) FROM venues").fetchone()[0] == 10


def test_load_seed_is_idempotent_and_uses_real_auth_hash(tmp_path):
    run_seed("scripts.seed", tmp_path)
    run_seed("scripts.seed_load_data", tmp_path)
    run_seed("scripts.seed_load_data", tmp_path)
    with closing(sqlite3.connect(tmp_path / "app.db")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 30
        assert connection.execute("SELECT COUNT(*) FROM participations").fetchone()[0] == 30
        password_hash = connection.execute("SELECT password_hash FROM users LIMIT 1").fetchone()[0]
    assert Argon2PasswordHasher().verify(TEST_PASSWORD, password_hash)


def test_demo_seed_does_not_depend_on_fixed_ids(db_session_factory):
    from app.db.models import VenueModel
    from scripts.seed import seed_venue

    with db_session_factory() as db:
        db.add(VenueModel(id=1, name="Sân khác", address="x", district_code="X", is_active=True))
        db.commit()

        assert seed_venue(db) == (10, 0)
        db.commit()
