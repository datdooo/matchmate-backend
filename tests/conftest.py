"""Shared real-SQLite fixtures for DB, participation and concurrency tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import ParticipationModel, SessionModel, UserModel, VenueModel
from app.db.session import create_session_factory, create_sqlite_engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.sessions.participation_repository import SQLiteParticipationUnitOfWorkFactory
from app.features.sessions.participation_service import ParticipationService

NOW = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FixedClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


@pytest.fixture
def session_factory(tmp_path: Path) -> sessionmaker[Session]:
    database_path = tmp_path / "matchmate-test.db"
    engine = create_sqlite_engine(
        f"sqlite:///{database_path}",
        busy_timeout_ms=2000,
    )
    Base.metadata.create_all(engine)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def service(session_factory: sessionmaker[Session]) -> ParticipationService:
    uow = SqlAlchemyUnitOfWork(session_factory)
    return ParticipationService(SQLiteParticipationUnitOfWorkFactory(uow), FixedClock())


def seed_user(
    session: Session,
    user_id: int,
    *,
    gender: str = "MALE",
    skill_level: int = 9,
    display_name: str | None = None,
) -> UserModel:
    user = UserModel(
        id=user_id,
        email=f"user{user_id}@example.test",
        password_hash="test-hash",
        display_name=display_name or f"Player {user_id:02d}",
        skill_level=skill_level,
        gender=gender,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )
    session.add(user)
    return user


def seed_venue(session: Session, venue_id: int = 1) -> VenueModel:
    venue = VenueModel(
        id=venue_id,
        name=f"Demo Venue {venue_id:02d}",
        address="Địa điểm giả lập để kiểm thử",
        district_code="DONG_DA",
        latitude=21.0285,
        longitude=105.8542,
        is_active=1,
    )
    session.add(venue)
    return venue


def seed_match_session(
    session: Session,
    session_id: int,
    host_user_id: int,
    *,
    venue_id: int = 1,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    play_type: str = "DOUBLES",
    status: str = "OPEN",
    fee_male_vnd: int = 80000,
    fee_female_vnd: int = 70000,
    min_level: int = 8,
    max_level: int = 10,
    gender_policy: str = "ANY",
) -> SessionModel:
    session.flush()
    starts = starts_at or (NOW + timedelta(hours=2))
    ends = ends_at or (starts + timedelta(hours=2))
    model = SessionModel(
        id=session_id,
        host_user_id=host_user_id,
        venue_id=venue_id,
        title=f"Kèo demo {session_id}",
        notes="Cầu TC77",
        starts_at=starts,
        ends_at=ends,
        play_type=play_type,
        fee_male_vnd=fee_male_vnd,
        fee_female_vnd=fee_female_vnd,
        min_level=min_level,
        max_level=max_level,
        gender_policy=gender_policy,
        status=status,
        created_at=NOW - timedelta(hours=1),
        cancelled_at=None,
    )
    session.add(model)
    return model


def seed_participation(
    session: Session,
    participation_id: int,
    user_id: int,
    session_id: int,
    *,
    status: str,
    gender: str = "MALE",
    quoted_fee_vnd: int = 80000,
) -> ParticipationModel:
    session.flush()
    decided_at = NOW - timedelta(minutes=30) if status in ("ACCEPTED", "REJECTED") else None
    cancelled_at = NOW - timedelta(minutes=15) if status == "CANCELLED" else None
    model = ParticipationModel(
        id=participation_id,
        user_id=user_id,
        session_id=session_id,
        status=status,
        created_at=NOW - timedelta(minutes=45),
        decided_at=decided_at,
        cancelled_at=cancelled_at,
        gender_at_join=gender,
        quoted_fee_vnd=quoted_fee_vnd,
    )
    session.add(model)
    return model
