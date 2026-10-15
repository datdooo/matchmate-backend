"""Concurrency invariants for serialized SQLite participation writes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from time import sleep

from sqlalchemy import func, select

from app.db.models import ParticipationModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.sessions.participation_contracts import ParticipationError
from app.features.sessions.participation_repository import SQLiteParticipationUnitOfWorkFactory
from app.features.sessions.participation_service import ParticipationService
from tests.conftest import NOW, seed_match_session, seed_participation, seed_user, seed_venue


def _run_together(*actions):
    barrier = Barrier(len(actions))

    def wrapped(action):
        barrier.wait(timeout=5)
        try:
            result = action()
            return ("ok", result.status)
        except ParticipationError as exc:
            return ("error", exc.code)

    with ThreadPoolExecutor(max_workers=len(actions)) as executor:
        futures = [executor.submit(wrapped, action) for action in actions]
        return [future.result(timeout=10) for future in futures]


def test_concurrent_approvals_never_exceed_capacity(session_factory, service) -> None:
    with session_factory() as session:
        for user_id in (1, 2, 3):
            seed_user(session, user_id)
        seed_venue(session)
        seed_match_session(session, 1, 1, play_type="SINGLES")
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 2, 1, status="PENDING")
        seed_participation(session, 3, 3, 1, status="PENDING")
        session.commit()

    outcomes = _run_together(
        lambda: service.decide(1, 2, "APPROVE"),
        lambda: service.decide(1, 3, "APPROVE"),
    )

    assert sorted(outcomes) == [("error", "SESSION_FULL"), ("ok", "ACCEPTED")]
    with session_factory() as session:
        accepted = session.scalar(
            select(func.count(ParticipationModel.id)).where(
                ParticipationModel.session_id == 1,
                ParticipationModel.status == "ACCEPTED",
            )
        )
        assert accepted == 2


def test_concurrent_approvals_never_accept_overlapping_sessions(session_factory, service) -> None:
    with session_factory() as session:
        for user_id in (1, 2, 10):
            seed_user(session, user_id)
        seed_venue(session)
        seed_match_session(session, 1, 1)
        seed_match_session(session, 2, 10)
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 10, 2, status="ACCEPTED")
        seed_participation(session, 3, 2, 1, status="PENDING")
        seed_participation(session, 4, 2, 2, status="PENDING")
        session.commit()

    outcomes = _run_together(
        lambda: service.decide(1, 3, "APPROVE"),
        lambda: service.decide(10, 4, "APPROVE"),
    )

    assert sorted(outcomes) == [("error", "TIME_CONFLICT"), ("ok", "ACCEPTED")]
    with session_factory() as session:
        accepted = session.scalar(
            select(func.count(ParticipationModel.id)).where(
                ParticipationModel.user_id == 2,
                ParticipationModel.status == "ACCEPTED",
            )
        )
        assert accepted == 1


def test_concurrent_approve_and_withdraw_leave_cancelled_history(session_factory, service) -> None:
    with session_factory() as session:
        seed_user(session, 1)
        seed_user(session, 2)
        seed_venue(session)
        seed_match_session(session, 1, 1)
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 2, 1, status="PENDING")
        session.commit()

    outcomes = sorted(
        _run_together(
            lambda: service.decide(1, 2, "APPROVE"),
            lambda: service.cancel(2, 2),
        )
    )

    assert outcomes in (
        [("error", "INVALID_STATE"), ("ok", "CANCELLED")],
        [("ok", "ACCEPTED"), ("ok", "CANCELLED")],
    )
    with session_factory() as session:
        participation = session.get(ParticipationModel, 2)
        assert participation is not None
        assert participation.status == "CANCELLED"
        accepted = session.scalar(
            select(func.count(ParticipationModel.id)).where(
                ParticipationModel.session_id == 1,
                ParticipationModel.status == "ACCEPTED",
            )
        )
        assert accepted == 1


class _MutableClock:
    def __init__(self) -> None:
        self.value = NOW

    def now(self):
        return self.value


def test_clock_is_read_after_begin_immediate_lock_is_acquired(session_factory) -> None:
    starts_at = NOW + timedelta(minutes=1)
    with session_factory() as session:
        seed_user(session, 1)
        seed_user(session, 2)
        seed_venue(session)
        seed_match_session(
            session,
            1,
            1,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=2),
        )
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 2, 1, status="PENDING")
        session.commit()

    clock = _MutableClock()
    service = ParticipationService(
        SQLiteParticipationUnitOfWorkFactory(SqlAlchemyUnitOfWork(session_factory)),
        clock,
    )
    holder = session_factory()
    holder.connection().exec_driver_sql("BEGIN IMMEDIATE")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(service.decide, 1, 2, "APPROVE")
            sleep(0.05)
            clock.value = starts_at
            holder.rollback()
            try:
                future.result(timeout=5)
            except ParticipationError as exc:
                assert exc.code == "SESSION_ALREADY_STARTED"
            else:
                raise AssertionError("decision must re-check time after obtaining the writer lock")
    finally:
        holder.rollback()
        holder.close()

    with session_factory() as session:
        participation = session.get(ParticipationModel, 2)
        assert participation is not None
        assert participation.status == "PENDING"
