"""Concurrency invariants for serialized SQLite APPROVE transactions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select

from app.db.models import ParticipationModel
from app.features.sessions.participation_contracts import ParticipationError
from tests.conftest import seed_match_session, seed_participation, seed_user, seed_venue


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
