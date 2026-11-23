from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.entities import Participation, Session
from app.domain.enums import (
    Gender,
    GenderPolicy,
    ParticipationStatus,
    PlayType,
    SessionStatus,
    SkillLevel,
    skill_to_rank,
)
from app.domain.errors import DomainError
from app.features.auth.contracts import PlayerProfile
from app.features.sessions.domain.policies import (
    require_decision_allowed,
    require_host_eligibility,
    require_player_eligibility,
    session_cancellation_time,
    should_withdraw,
)
from app.features.sessions.session_contracts import CreateSessionInput, SessionError

STARTS_AT = datetime(2030, 11, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def game() -> Session:
    return Session(
        id=1,
        host_user_id=1,
        venue_id=1,
        title="Test session",
        notes="",
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + timedelta(hours=2),
        play_type=PlayType.DOUBLES,
        fee_male_vnd=60_000,
        fee_female_vnd=40_000,
        min_level=skill_to_rank(SkillLevel.TB_MINUS),
        max_level=skill_to_rank(SkillLevel.TB_PLUS),
        gender_policy=GenderPolicy.FEMALE_ONLY,
        status=SessionStatus.OPEN,
        created_at=STARTS_AT - timedelta(hours=2),
        cancelled_at=None,
    )


@pytest.fixture
def create_input(game) -> CreateSessionInput:
    return CreateSessionInput(
        venue_id=game.venue_id,
        title=game.title,
        starts_at=game.starts_at,
        ends_at=game.ends_at,
        play_type="DOUBLES",
        fee_male_vnd=game.fee_male_vnd,
        fee_female_vnd=game.fee_female_vnd,
        min_level=SkillLevel.TB_MINUS,
        max_level=SkillLevel.TB_PLUS,
        gender_policy="FEMALE_ONLY",
    )


@pytest.fixture
def pending(game) -> Participation:
    return Participation(
        id=1,
        user_id=2,
        session_id=game.id,
        status=ParticipationStatus.PENDING,
        gender_at_join=Gender.FEMALE,
        quoted_fee_vnd=40_000,
        created_at=game.created_at,
        decided_at=None,
        cancelled_at=None,
    )


@pytest.mark.parametrize("skill", [SkillLevel.TB_MINUS, SkillLevel.TB_PLUS])
def test_host_and_player_eligibility_include_both_rank_boundaries(game, create_input, skill):
    profile = PlayerProfile(1, "Player", skill, Gender.FEMALE)

    require_host_eligibility(profile, create_input)
    require_player_eligibility(profile, game)


@pytest.mark.parametrize(
    "skill,gender,code",
    [
        (SkillLevel.TB, Gender.UNSPECIFIED, "PROFILE_INCOMPLETE"),
        (SkillLevel.TB, Gender.MALE, "ELIGIBILITY_MISMATCH"),
        (SkillLevel.TBY_PLUS, Gender.FEMALE, "ELIGIBILITY_MISMATCH"),
        (SkillLevel.TBK_MINUS, Gender.FEMALE, "ELIGIBILITY_MISMATCH"),
    ],
)
def test_host_and_player_eligibility_reject_incomplete_or_outside_requirements(
    game, create_input, skill, gender, code
):
    profile = PlayerProfile(1, "Player", skill, gender)

    with pytest.raises(SessionError) as host_error:
        require_host_eligibility(profile, create_input)
    with pytest.raises(DomainError) as player_error:
        require_player_eligibility(profile, game)

    assert host_error.value.code == player_error.value.code == code


def test_host_eligibility_rejects_inverted_rank_range(create_input):
    profile = PlayerProfile(1, "Host", SkillLevel.TB, Gender.FEMALE)
    data = replace(create_input, min_level=SkillLevel.TB_PLUS, max_level=SkillLevel.TB_MINUS)

    with pytest.raises(SessionError) as error:
        require_host_eligibility(profile, data)

    assert error.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "actor_id,participation_status,session_status,code",
    [
        (2, ParticipationStatus.ACCEPTED, SessionStatus.CANCELLED, "FORBIDDEN"),
        (1, ParticipationStatus.ACCEPTED, SessionStatus.CANCELLED, "INVALID_STATE"),
        (1, ParticipationStatus.PENDING, SessionStatus.CANCELLED, "SESSION_CANCELLED"),
        (1, ParticipationStatus.PENDING, SessionStatus.OPEN, "SESSION_ALREADY_STARTED"),
    ],
)
def test_decision_checks_owner_then_state_then_session(
    game, pending, actor_id, participation_status, session_status, code
):
    with pytest.raises(DomainError) as error:
        require_decision_allowed(
            replace(game, status=session_status),
            replace(pending, status=participation_status),
            actor_id,
            now=game.starts_at,
        )

    assert error.value.code == code


def test_pending_participation_can_be_decided_before_start(game, pending):
    require_decision_allowed(game, pending, game.host_user_id, now=game.created_at)


@pytest.mark.parametrize("status", [ParticipationStatus.PENDING, ParticipationStatus.ACCEPTED])
def test_player_can_withdraw_active_participation_before_start(game, pending, status):
    assert should_withdraw(
        game, replace(pending, status=status), pending.user_id, now=game.created_at
    )


def test_repeated_withdrawal_checks_owner_before_returning_existing_record(game, pending):
    cancelled = replace(pending, status=ParticipationStatus.CANCELLED)

    assert not should_withdraw(game, cancelled, pending.user_id, now=game.starts_at)
    with pytest.raises(DomainError) as error:
        should_withdraw(game, cancelled, game.host_user_id, now=game.starts_at)

    assert error.value.code == "FORBIDDEN"


def test_session_cancellation_respects_start_time_and_existing_cancellation(game, clock):
    host_id = game.host_user_id
    inputs = {"host_id": host_id, "starts_at": game.starts_at, "clock": clock}
    cancelled_at = session_cancellation_time(**inputs, actor_id=host_id, status=SessionStatus.OPEN)
    assert cancelled_at == clock.now()

    clock.value = game.starts_at
    with pytest.raises(SessionError) as started:
        session_cancellation_time(**inputs, actor_id=host_id, status=SessionStatus.OPEN)
    assert started.value.code == "SESSION_ALREADY_STARTED"

    already_cancelled = session_cancellation_time(
        **inputs, actor_id=host_id, status=SessionStatus.CANCELLED
    )
    assert already_cancelled is None
    with pytest.raises(SessionError) as forbidden:
        session_cancellation_time(**inputs, actor_id=2, status=SessionStatus.CANCELLED)
    assert forbidden.value.code == "FORBIDDEN"
