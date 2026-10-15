"""FR-08/09/10 integration tests against a real SQLite database."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.models import MatchingRequestModel, ParticipationModel, UserModel
from app.features.sessions.participation_contracts import ParticipationError
from tests.conftest import (
    NOW,
    seed_match_session,
    seed_participation,
    seed_user,
    seed_venue,
)


def _seed_basic_session(session_factory, *, play_type: str = "DOUBLES") -> None:
    with session_factory() as session:
        seed_user(session, 1, gender="MALE", display_name="Host")
        seed_user(session, 2, gender="FEMALE", display_name="Player")
        seed_user(session, 3, gender="MALE", display_name="Player 3")
        seed_venue(session)
        seed_match_session(session, 1, 1, play_type=play_type)
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        session.commit()


def test_join_creates_pending_with_immutable_fee_snapshot(session_factory, service) -> None:
    _seed_basic_session(session_factory)

    detail = service.join(actor_user_id=2, session_id=1)

    assert detail.status == "PENDING"
    assert detail.gender_at_join == "FEMALE"
    assert detail.quoted_fee_vnd == 70000
    assert detail.can_cancel is True
    assert detail.can_decide is False
    assert detail.session.accepted_count == 1
    assert detail.session.remaining_capacity == 3
    assert detail.session.host.display_name == "Host"
    assert detail.session.venue.distance_km is None

    with session_factory() as session:
        user = session.get(UserModel, 2)
        assert user is not None
        user.gender = "MALE"
        session.commit()

    with pytest.raises(ParticipationError) as exc_info:
        service.join(actor_user_id=2, session_id=1)
    assert exc_info.value.code == "PARTICIPATION_ALREADY_EXISTS"

    with session_factory() as session:
        stored = session.scalar(
            select(ParticipationModel).where(
                ParticipationModel.user_id == 2,
                ParticipationModel.session_id == 1,
            )
        )
        assert stored is not None
        assert stored.gender_at_join == "FEMALE"
        assert stored.quoted_fee_vnd == 70000


def test_pending_requests_do_not_reserve_capacity(session_factory, service) -> None:
    _seed_basic_session(session_factory, play_type="SINGLES")

    first = service.join(2, 1)
    second = service.join(3, 1)

    assert first.status == "PENDING"
    assert second.status == "PENDING"
    assert second.session.accepted_count == 1
    assert second.session.remaining_capacity == 1


def test_join_rejects_accepted_time_overlap(session_factory, service) -> None:
    with session_factory() as session:
        for user_id in (1, 2, 3):
            seed_user(session, user_id)
        seed_venue(session)
        seed_match_session(session, 1, 1)
        seed_match_session(session, 2, 3)
        seed_participation(session, 1, 1, 1, status="ACCEPTED")
        seed_participation(session, 2, 3, 2, status="ACCEPTED")
        seed_participation(session, 3, 2, 2, status="ACCEPTED")
        session.commit()

    with pytest.raises(ParticipationError) as exc_info:
        service.join(2, 1)
    assert exc_info.value.code == "TIME_CONFLICT"


def test_approve_rechecks_capacity_and_closes_overlapping_matching(
    session_factory, service
) -> None:
    _seed_basic_session(session_factory, play_type="SINGLES")
    pending = service.join(2, 1)

    with session_factory() as session:
        session.add(
            MatchingRequestModel(
                id=1,
                user_id=2,
                venue_id=1,
                starts_at=NOW + timedelta(hours=1),
                ends_at=NOW + timedelta(hours=5),
                play_type="SINGLES",
                proposed_fee_male_vnd=80000,
                proposed_fee_female_vnd=70000,
                budget_max_vnd=90000,
                gender_policy="ANY",
                status="ACTIVE",
                closed_reason=None,
                created_at=NOW - timedelta(minutes=20),
                closed_at=None,
            )
        )
        session.commit()

    approved = service.decide(1, pending.id, "APPROVE")
    assert approved.status == "ACCEPTED"
    assert approved.decided_at == NOW
    assert approved.quoted_fee_vnd == 70000
    assert approved.session.accepted_count == 2
    assert approved.session.remaining_capacity == 0

    with session_factory() as session:
        request = session.get(MatchingRequestModel, 1)
        assert request is not None
        assert request.status == "CLOSED"
        assert request.closed_reason == "CONFIRMED"
        assert request.closed_at == NOW


def test_reject_does_not_recheck_capacity_or_eligibility(session_factory, service) -> None:
    _seed_basic_session(session_factory, play_type="SINGLES")
    pending = service.join(2, 1)

    with session_factory() as session:
        player = session.get(UserModel, 2)
        assert player is not None
        player.skill_level = 1
        seed_participation(session, 50, 3, 1, status="ACCEPTED")
        session.commit()

    rejected = service.decide(1, pending.id, "REJECT")
    assert rejected.status == "REJECTED"
    assert rejected.decided_at == NOW


def test_second_approval_sees_session_full(session_factory, service) -> None:
    _seed_basic_session(session_factory, play_type="SINGLES")
    p2 = service.join(2, 1)
    p3 = service.join(3, 1)

    service.decide(1, p2.id, "APPROVE")
    with pytest.raises(ParticipationError) as exc_info:
        service.decide(1, p3.id, "APPROVE")
    assert exc_info.value.code == "SESSION_FULL"


def test_cancel_is_idempotent_and_host_cannot_withdraw(session_factory, service) -> None:
    _seed_basic_session(session_factory)
    pending = service.join(2, 1)

    cancelled = service.cancel(2, pending.id)
    again = service.cancel(2, pending.id)
    assert cancelled.status == "CANCELLED"
    assert again.status == "CANCELLED"
    assert again.cancelled_at == NOW

    with pytest.raises(ParticipationError) as exc_info:
        service.cancel(1, 1)
    assert exc_info.value.code == "HOST_PARTICIPATION_REQUIRED"


def test_cancel_checks_owner_before_idempotent_return(session_factory, service) -> None:
    _seed_basic_session(session_factory)
    pending = service.join(2, 1)
    service.cancel(2, pending.id)

    with pytest.raises(ParticipationError) as exc_info:
        service.cancel(3, pending.id)
    assert exc_info.value.code == "FORBIDDEN"
