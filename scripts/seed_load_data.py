import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db.base import Base
from app.db.models import (
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.session import create_session_factory, engine
from app.features.auth.security import Argon2PasswordHasher

N_SINGLES = 9
N_DOUBLES = 21
N_SESSIONS = N_SINGLES + N_DOUBLES

N_EXTRA_USERS = 10  # user ngoài host
USER_PREFIX = "loadtest_"
EMAIL_DOMAIN = "example.com"
TEST_PASSWORD = "LoadTest@123"

LOADTEST_TAG = "[LOADTEST]"

# Giờ địa phương
LOCAL_TZ = timezone(timedelta(hours=7))
# Bắt đầu và thời lượng phút của 2 khung chính.
TIME_SLOTS = [(19, 30, 120), (20, 0, 120)]
# Ca biên.
EDGE_CASES = {0: 60, 1: 240}
DAYS_AHEAD = 7  # rải kèo vào 1..7 ngày tới

# Phí (nam, nữ)
FEE_PAIRS = [
    (50_000, 50_000),
    (60_000, 40_000),
    (0, 0),
    (70_000, 50_000),
    (40_000, 60_000),
]
GENDER_POLICIES = ["ANY", "ANY", "MALE_ONLY", "ANY", "FEMALE_ONLY"]


def hash_password(password: str) -> str:
    return Argon2PasswordHasher().hash(password)


def build_user_specs(extra_users: int = N_EXTRA_USERS) -> list[dict]:
    specs = []

    for i in range(N_SESSIONS + extra_users):
        n = i + 1
        specs.append(
            {
                "email": f"{USER_PREFIX}{n:03d}@{EMAIL_DOMAIN}",
                "display_name": f"{LOADTEST_TAG}{n:03d}",
                "gender": "MALE" if i % 2 == 0 else "FEMALE",
                "skill_level": 1 + (i * 7) % 19,
            }
        )

    return specs


def make_start_time(day_offset: int, hour: int, minute: int, now: datetime) -> datetime:
    local_today = now.astimezone(LOCAL_TZ).date() + timedelta(days=day_offset)
    local_dt = datetime(
        local_today.year,
        local_today.month,
        local_today.day,
        hour,
        minute,
        tzinfo=LOCAL_TZ,
    )
    return local_dt.astimezone(timezone.utc)


def build_session_specs(user_specs: list[dict], now: datetime) -> list[dict]:
    specs = []
    for i in range(N_SESSIONS):
        host = user_specs[i]

        play_type = "SINGLES" if i % 10 in (0, 3, 6) else "DOUBLES"

        hour, minute, duration = TIME_SLOTS[i % len(TIME_SLOTS)]
        duration = EDGE_CASES.get(i, duration)
        starts_at = make_start_time(1 + i % DAYS_AHEAD, hour, minute, now)
        ends_at = starts_at + timedelta(minutes=duration)

        fee_male, fee_female = FEE_PAIRS[i % len(FEE_PAIRS)]

        policy = GENDER_POLICIES[i % len(GENDER_POLICIES)]
        if (policy == "MALE_ONLY" and host["gender"] != "MALE") or (
            policy == "FEMALE_ONLY" and host["gender"] != "FEMALE"
        ):
            policy = "ANY"

        level = host["skill_level"]
        min_level = max(1, level - 3)
        max_level = min(19, level + 3 + i % 3)

        specs.append(
            {
                "host_index": i,
                "venue_index": i,
                "title": f"{LOADTEST_TAG} Kèo {i + 1:02d} - {play_type}",
                "notes": "Dữ liệu tạo tự động để kiểm thử",
                "play_type": play_type,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "fee_male_vnd": fee_male,
                "fee_female_vnd": fee_female,
                "min_level": min_level,
                "max_level": max_level,
                "gender_policy": policy,
            }
        )

    counts = Counter(s["play_type"] for s in specs)
    assert counts["SINGLES"] == N_SINGLES and counts["DOUBLES"] == N_DOUBLES, counts
    return specs


def check_target_db() -> None:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    if not database_url.startswith("sqlite:///"):
        raise SystemExit("Từ chối chạy: script này chỉ dành cho SQLite local.")


def get_venues(db) -> list[VenueModel]:
    venues = list(
        db.scalars(select(VenueModel).where(VenueModel.is_active.is_(True)).order_by(VenueModel.id))
    )

    if not venues:
        raise SystemExit("Chưa có sân. Hãy chạy trước: python -m scripts.seed")
    return venues


def already_seeded(db) -> int:
    return db.scalar(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.title.like(f"{LOADTEST_TAG}%"))
    )


def make_users(db, user_specs: list[dict], now: datetime) -> list[UserModel]:
    password_hash = hash_password(TEST_PASSWORD)
    users = []

    for spec in user_specs:
        user = db.scalar(select(UserModel).where(UserModel.email == spec["email"]))
        if user is None:
            user = UserModel(
                email=spec["email"],
                password_hash=password_hash,
                display_name=spec["display_name"],
                skill_level=spec["skill_level"],
                gender=spec["gender"],
                created_at=now,
                updated_at=now,
            )
            db.add(user)
        users.append(user)
    db.flush()
    return users


def create_sessions(
    db,
    specs: list[dict],
    venues: list[VenueModel],
    hosts: list[UserModel],
    now: datetime,
) -> None:
    sessions = []

    for spec in specs:
        host = hosts[spec["host_index"]]
        venue = venues[spec["venue_index"] % len(venues)]
        session = SessionModel(
            host_user_id=host.id,
            venue_id=venue.id,
            title=spec["title"],
            notes=spec["notes"],
            starts_at=spec["starts_at"],
            ends_at=spec["ends_at"],
            play_type=spec["play_type"],
            fee_male_vnd=spec["fee_male_vnd"],
            fee_female_vnd=spec["fee_female_vnd"],
            min_level=spec["min_level"],
            max_level=spec["max_level"],
            gender_policy=spec["gender_policy"],
            status="OPEN",
            created_at=now,
            cancelled_at=None,
        )
        db.add(session)
        sessions.append((session, host, spec))
    db.flush()

    for session, host, spec in sessions:
        fee = spec["fee_male_vnd"] if host.gender == "MALE" else spec["fee_female_vnd"]
        db.add(
            ParticipationModel(
                user_id=host.id,
                session_id=session.id,
                status="ACCEPTED",
                gender_at_join=host.gender,
                quoted_fee_vnd=fee,
                created_at=now,
                decided_at=now,
                cancelled_at=None,
            )
        )


def print_summary(db) -> None:
    rows = db.execute(
        select(SessionModel.play_type, SessionModel.starts_at, SessionModel.ends_at).where(
            SessionModel.title.like(f"{LOADTEST_TAG}%")
        )
    ).all()
    by_type = Counter(r.play_type for r in rows)
    durations = Counter(int((r.ends_at - r.starts_at).total_seconds() // 60) for r in rows)
    print(f"Tổng kèo load test: {len(rows)}")
    print(f"  SINGLES: {by_type['SINGLES']}, DOUBLES: {by_type['DOUBLES']}")
    print(f"  Ca biên: 60 phút = {durations[60]}, 240 phút = {durations[240]}")


def main() -> None:
    check_target_db()

    session_factory = create_session_factory(engine)
    Base.metadata.create_all(engine)

    now = datetime.now(timezone.utc)

    user_specs = build_user_specs()
    session_specs = build_session_specs(user_specs, now)

    with session_factory() as db:
        venues = get_venues(db)

        existing = already_seeded(db)
        if existing:
            print(f"Đã có {existing} kèo load test")
            print_summary(db)
            return

        hosts = make_users(db, user_specs, now)
        create_sessions(db, session_specs, venues, hosts, now)
        db.commit()

        print_summary(db)


if __name__ == "__main__":
    main()
