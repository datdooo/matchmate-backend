from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.models import MatchingRequestModel, ParticipationModel, SessionModel, UserModel
from app.domain.errors import DomainError


def expect_error(code, operation):
    with pytest.raises(DomainError) as caught:
        operation()
    assert caught.value.code == code


def test_join_is_pending_and_does_not_hold_capacity(service, game_data):
    result = service.join(game_data["player"], game_data["first"])
    assert result.status == "PENDING"
    assert (result.gender_at_join, result.quoted_fee_vnd) == ("FEMALE", 40000)
    assert (result.session.accepted_count, result.session.remaining_capacity) == (1, 3)
    assert result.can_cancel and not result.can_decide
    assert result.decided_at is None and result.cancelled_at is None
    expect_error(
        "PARTICIPATION_ALREADY_EXISTS",
        lambda: service.join(game_data["player"], game_data["first"]),
    )
    expect_error(
        "PARTICIPATION_ALREADY_EXISTS", lambda: service.join(game_data["host"], game_data["first"])
    )


def test_pending_may_overlap_but_accepted_may_not(service, game_data, db_session_factory):
    with db_session_factory() as session:
        first = session.get(SessionModel, game_data["first"])
        second = session.get(SessionModel, game_data["second"])
        second.starts_at = first.starts_at + timedelta(minutes=30)
        session.commit()
    first = service.join(game_data["player"], game_data["first"])
    second = service.join(game_data["player"], game_data["second"])
    service.decide(game_data["host"], first.id, "APPROVE")
    expect_error("TIME_CONFLICT", lambda: service.decide(game_data["host"], second.id, "APPROVE"))
    with db_session_factory() as session:
        assert session.get(ParticipationModel, second.id).status == "PENDING"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("gender", "UNSPECIFIED", "PROFILE_INCOMPLETE"),
        ("skill_level", 7, "ELIGIBILITY_MISMATCH"),
        ("gender", "MALE", "ELIGIBILITY_MISMATCH"),
    ],
)
def test_join_checks_current_profile(service, game_data, db_session_factory, field, value, code):
    with db_session_factory() as session:
        session.get(SessionModel, game_data["first"]).gender_policy = "FEMALE_ONLY"
        setattr(session.get(UserModel, game_data["player"]), field, value)
        session.commit()
    expect_error(code, lambda: service.join(game_data["player"], game_data["first"]))


@pytest.mark.parametrize("cancelled", [False, True])
def test_join_rejects_started_or_cancelled(
    service, game_data, db_session_factory, clock, cancelled
):
    with db_session_factory() as session:
        game = session.get(SessionModel, game_data["first"])
        if cancelled:
            game.status, game.cancelled_at = "CANCELLED", clock.value
        else:
            clock.value = game.starts_at
        session.commit()
    expect_error(
        "SESSION_CANCELLED" if cancelled else "SESSION_ALREADY_STARTED",
        lambda: service.join(game_data["player"], game_data["first"]),
    )


def test_approve_rechecks_profile_but_keeps_quote(service, game_data, db_session_factory, clock):
    pending = service.join(game_data["player"], game_data["first"])
    with db_session_factory() as session:
        game = session.get(SessionModel, game_data["first"])
        game.fee_female_vnd = 99999
        session.get(UserModel, game_data["player"]).gender = "MALE"
        request = MatchingRequestModel(
            user_id=game_data["player"],
            venue_id=game_data["venue"],
            starts_at=game.starts_at,
            ends_at=game.ends_at,
            play_type="DOUBLES",
            proposed_fee_male_vnd=60000,
            proposed_fee_female_vnd=40000,
            budget_max_vnd=80000,
            gender_policy="ANY",
            status="ACTIVE",
            created_at=clock.value,
        )
        session.add(request)
        session.commit()
        request_id = request.id
    approved = service.decide(game_data["host"], pending.id, "APPROVE")
    assert approved.status == "ACCEPTED" and approved.decided_at == clock.value
    assert (approved.gender_at_join, approved.quoted_fee_vnd) == ("FEMALE", 40000)
    assert approved.player.gender == "MALE"
    assert approved.session.accepted_count == 2
    assert not approved.can_decide
    with db_session_factory() as session:
        saved = session.get(MatchingRequestModel, request_id)
        assert (saved.status, saved.closed_reason) == ("CLOSED", "CONFIRMED")
    expect_error("INVALID_STATE", lambda: service.decide(game_data["host"], pending.id, "REJECT"))


def test_reject_skips_capacity_and_eligibility(service, game_data, db_session_factory, clock):
    pending = service.join(game_data["player"], game_data["first"])
    with db_session_factory() as session:
        session.get(SessionModel, game_data["first"]).play_type = "SINGLES"
        session.get(UserModel, game_data["player"]).gender = "UNSPECIFIED"
        session.add(
            ParticipationModel(
                user_id=game_data["other"],
                session_id=game_data["first"],
                status="ACCEPTED",
                gender_at_join="MALE",
                quoted_fee_vnd=60000,
                created_at=clock.value,
                decided_at=clock.value,
            )
        )
        session.commit()
    rejected = service.decide(game_data["host"], pending.id, "REJECT")
    assert rejected.status == "REJECTED" and rejected.quoted_fee_vnd == 40000
    expect_error("INVALID_STATE", lambda: service.withdraw(game_data["player"], pending.id))


def test_approve_rechecks_capacity_and_profile(service, game_data, db_session_factory, clock):
    pending = service.join(game_data["player"], game_data["first"])
    other = service.join(game_data["other"], game_data["first"])
    with db_session_factory() as session:
        session.get(SessionModel, game_data["first"]).play_type = "SINGLES"
        session.commit()
    service.decide(game_data["host"], other.id, "APPROVE")
    expect_error("SESSION_FULL", lambda: service.decide(game_data["host"], pending.id, "APPROVE"))
    expect_error("SESSION_FULL", lambda: service.join(game_data["player"], game_data["first"]))
    service.withdraw(game_data["other"], other.id)
    with db_session_factory() as session:
        session.get(UserModel, game_data["player"]).skill_level = 1
        session.commit()
    expect_error(
        "ELIGIBILITY_MISMATCH", lambda: service.decide(game_data["host"], pending.id, "APPROVE")
    )


@pytest.mark.parametrize("accepted", [False, True])
def test_withdraw_is_idempotent_before_time_check(service, game_data, clock, accepted):
    pending = service.join(game_data["player"], game_data["first"])
    if accepted:
        service.decide(game_data["host"], pending.id, "APPROVE")
    cancelled = service.withdraw(game_data["player"], pending.id)
    assert cancelled.status == "CANCELLED" and cancelled.session.accepted_count == 1
    assert cancelled.quoted_fee_vnd == 40000 and not cancelled.can_cancel
    clock.value += timedelta(days=1)
    again = service.withdraw(game_data["player"], pending.id)
    assert again.cancelled_at == cancelled.cancelled_at
    expect_error("FORBIDDEN", lambda: service.withdraw(game_data["other"], pending.id))
    expect_error("INVALID_STATE", lambda: service.decide(game_data["host"], pending.id, "APPROVE"))


def test_existence_and_permissions(service, game_data, db_session_factory):
    expect_error("SESSION_NOT_FOUND", lambda: service.join(game_data["player"], 9999))
    expect_error("PARTICIPATION_NOT_FOUND", lambda: service.withdraw(game_data["player"], 9999))
    expect_error(
        "PARTICIPATION_NOT_FOUND", lambda: service.decide(game_data["host"], 9999, "APPROVE")
    )
    pending = service.join(game_data["player"], game_data["first"])
    expect_error("FORBIDDEN", lambda: service.decide(game_data["player"], pending.id, "APPROVE"))
    expect_error("FORBIDDEN", lambda: service.withdraw(game_data["host"], pending.id))
    with db_session_factory() as session:
        host_part = session.scalar(
            select(ParticipationModel.id).where(
                ParticipationModel.session_id == game_data["first"],
                ParticipationModel.user_id == game_data["host"],
            )
        )
    expect_error(
        "HOST_PARTICIPATION_REQUIRED", lambda: service.withdraw(game_data["host"], host_part)
    )


def test_rejoin_creates_new_history_record(service, game_data):
    first = service.join(game_data["player"], game_data["first"])
    service.withdraw(game_data["player"], first.id)
    second = service.join(game_data["player"], game_data["first"])
    assert first.id != second.id and second.status == "PENDING"


def test_approve_rejects_newly_incomplete_profile(service, game_data, db_session_factory):
    pending = service.join(game_data["player"], game_data["first"])
    with db_session_factory() as session:
        session.get(UserModel, game_data["player"]).gender = "UNSPECIFIED"
        session.commit()
    expect_error(
        "PROFILE_INCOMPLETE", lambda: service.decide(game_data["host"], pending.id, "APPROVE")
    )
