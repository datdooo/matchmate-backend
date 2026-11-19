"""Create a synthetic SQLite migration source and a non-sensitive manifest.

Never reads the application's local DB; refuses to overwrite an existing output.
Run: python -m scripts.prepare_member2_phase1
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.db.base import Base
from app.db.models import (
    MatchingRequestModel,
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.session import create_db_engine, create_session_factory


def prepare(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = output / "migration-source.db"
    manifest_path = output / "migration-source.manifest.json"
    if source.exists() or manifest_path.exists():
        raise FileExistsError("Choose a new output directory; existing evidence is preserved")
    now = datetime(2030, 11, 1, 10, 0, 0, 123456, tzinfo=timezone.utc)
    starts = now + timedelta(hours=2)
    ends = starts + timedelta(hours=2)
    engine = create_db_engine(f"sqlite:///{source.resolve().as_posix()}")
    try:
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory.begin() as db:
            db.add(
                VenueModel(
                    id=10,
                    name="Migration demo",
                    address="Synthetic",
                    district_code="CAU_GIAY",
                    is_active=True,
                )
            )
            db.add_all(
                [
                    UserModel(
                        id=uid,
                        email=f"migration-{uid}@example.invalid",
                        password_hash="synthetic-not-a-login-hash",
                        display_name=f"Player {uid}",
                        skill_level=9,
                        gender=gender,
                        created_at=now,
                        updated_at=now,
                    )
                    for uid, gender in [(20, "MALE"), (30, "FEMALE"), (40, "UNSPECIFIED")]
                ]
            )
            db.flush()
            db.add(
                SessionModel(
                    id=50,
                    host_user_id=20,
                    venue_id=10,
                    title="Migration fixture",
                    notes="",
                    starts_at=starts,
                    ends_at=ends,
                    play_type="DOUBLES",
                    fee_male_vnd=60000,
                    fee_female_vnd=40000,
                    min_level=8,
                    max_level=10,
                    gender_policy="ANY",
                    status="OPEN",
                    created_at=now,
                )
            )
            db.flush()
            for pid, uid, status, gender, fee in [
                (60, 20, "ACCEPTED", "MALE", 60000),
                (70, 30, "REJECTED", "FEMALE", 40000),
                (80, 30, "CANCELLED", "FEMALE", 40000),
                (90, 30, "ACCEPTED", "FEMALE", 40000),
            ]:
                db.add(
                    ParticipationModel(
                        id=pid,
                        user_id=uid,
                        session_id=50,
                        status=status,
                        gender_at_join=gender,
                        quoted_fee_vnd=fee,
                        created_at=now,
                        decided_at=now if status != "CANCELLED" else None,
                        cancelled_at=now if status == "CANCELLED" else None,
                    )
                )
            for mid, status, reason in [
                (100, "CLOSED", "REPLACED"),
                (110, "CLOSED", "CONFIRMED"),
                (120, "ACTIVE", None),
            ]:
                db.add(
                    MatchingRequestModel(
                        id=mid,
                        user_id=40,
                        venue_id=10,
                        starts_at=starts,
                        ends_at=ends,
                        play_type="DOUBLES",
                        proposed_fee_male_vnd=60000,
                        proposed_fee_female_vnd=40000,
                        budget_max_vnd=70000,
                        gender_policy="ANY",
                        status=status,
                        closed_reason=reason,
                        created_at=now,
                        closed_at=now if status == "CLOSED" else None,
                    )
                )
        with factory() as db:
            counts = {
                table.name: db.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }
            foreign_key_errors = db.connection().exec_driver_sql("PRAGMA foreign_key_check").all()
            integrity = db.connection().exec_driver_sql("PRAGMA integrity_check").scalar()
            if foreign_key_errors or integrity != "ok":
                raise RuntimeError("Fixture integrity check failed")
            timestamps = dict(
                db.connection()
                .exec_driver_sql("SELECT id, created_at FROM users ORDER BY id")
                .all()
            )
        manifest = {
            "synthetic": True,
            "counts": counts,
            "max_ids": {
                "venues": 10,
                "users": 40,
                "sessions": 50,
                "participations": 90,
                "matching_requests": 120,
            },
            "user_created_at_raw": timestamps,
            "participation_ids": {"accepted": [60, 90], "rejected": [70], "cancelled": [80]},
            "matching_ids": {"replaced": [100], "confirmed": [110], "active": [120]},
            "foreign_key_check": "ok",
            "integrity_check": integrity,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return manifest
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/member2-phase1"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
