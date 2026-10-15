"""DB/UoW contract tests owned by the participation/transaction slice."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import ParticipationModel, UserModel
from app.db.session import create_session_factory, create_sqlite_engine
from app.db.types import from_db_utc, to_db_utc
from app.db.unit_of_work import DatabaseBusy, SqlAlchemyUnitOfWork, is_sqlite_busy
from tests.conftest import NOW, seed_match_session, seed_participation, seed_user, seed_venue


def test_utc_mapper_uses_one_fixed_z_format() -> None:
    value = datetime(2026, 10, 15, 7, 30, 1, 1234, tzinfo=timezone(timedelta(hours=7)))
    stored = to_db_utc(value)
    assert stored == "2026-10-15T00:30:01.001234Z"
    assert from_db_utc(stored) == datetime(2026, 10, 15, 0, 30, 1, 1234, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        to_db_utc(datetime(2026, 10, 15, 0, 30))


def test_sqlite_connections_enable_foreign_keys_and_busy_timeout(session_factory) -> None:
    with session_factory() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
        assert session.scalar(text("PRAGMA busy_timeout")) == 2000


def test_active_participation_unique_is_partial(session_factory) -> None:
    with session_factory() as session:
        seed_user(session, 1)
        seed_user(session, 2)
        seed_venue(session)
        seed_match_session(session, 1, 1)
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 2, 1, status="PENDING")
        session.commit()

        duplicate = ParticipationModel(
            user_id=2,
            session_id=1,
            status="ACCEPTED",
            created_at=NOW,
            decided_at=NOW,
            cancelled_at=None,
            gender_at_join="MALE",
            quoted_fee_vnd=80000,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        pending = session.get(ParticipationModel, 2)
        assert pending is not None
        pending.status = "CANCELLED"
        pending.cancelled_at = NOW
        session.commit()

        replacement = ParticipationModel(
            user_id=2,
            session_id=1,
            status="PENDING",
            created_at=NOW,
            decided_at=None,
            cancelled_at=None,
            gender_at_join="MALE",
            quoted_fee_vnd=80000,
        )
        session.add(replacement)
        session.commit()


def test_write_uow_rolls_back_when_block_raises(session_factory) -> None:
    uow = SqlAlchemyUnitOfWork(session_factory)
    with pytest.raises(RuntimeError):
        with uow.write() as transaction:
            seed_user(transaction.session, 99, display_name="Rollback")
            raise RuntimeError("boom")

    with session_factory() as session:
        assert session.get(UserModel, 99) is None


def test_busy_write_maps_to_database_busy(tmp_path) -> None:
    engine = create_sqlite_engine(
        f"sqlite:///{tmp_path / 'busy.db'}",
        busy_timeout_ms=25,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    holder = factory()
    try:
        holder.connection().exec_driver_sql("BEGIN IMMEDIATE")
        uow = SqlAlchemyUnitOfWork(factory)
        with pytest.raises(DatabaseBusy):
            with uow.write():
                pass
    finally:
        holder.rollback()
        holder.close()
        engine.dispose()


def test_sqlite_locked_is_not_misclassified_as_database_busy() -> None:
    error = sqlite3.OperationalError("database table is locked")
    error.sqlite_errorcode = sqlite3.SQLITE_LOCKED
    error.sqlite_errorname = "SQLITE_LOCKED"

    assert is_sqlite_busy(error) is False
