from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.enums import Gender, GenderPolicy, MatchingStatus, PlayType
from app.features.matching.contracts import MatchingCandidate, MatchingRequestRecord, PlayerSummary
from app.features.matching.strategy import find_group

NOW = datetime(2030, 11, 2, 10, tzinfo=timezone.utc)
CALLER = PlayerSummary(id=100, display_name="Caller", skill_level=9, gender=Gender.MALE)
REQUEST = MatchingRequestRecord(
    id=901,
    user_id=CALLER.id,
    venue_id=10,
    starts_at=NOW + timedelta(hours=2),
    ends_at=NOW + timedelta(hours=4),
    play_type=PlayType.SINGLES,
    proposed_fee_male_vnd=60_000,
    proposed_fee_female_vnd=40_000,
    budget_max_vnd=60_000,
    gender_policy=GenderPolicy.ANY,
    status=MatchingStatus.ACTIVE,
    closed_reason=None,
    created_at=NOW,
    closed_at=None,
)


def candidate(
    request_id=200,
    user_id=201,
    *,
    rank=9,
    gender=Gender.MALE,
    policy=GenderPolicy.ANY,
    budget=60_000,
    minute=1,
):
    return MatchingCandidate(
        player=PlayerSummary(user_id, f"Player {user_id}", rank, gender),
        request=replace(
            REQUEST,
            id=request_id,
            user_id=user_id,
            gender_policy=policy,
            budget_max_vnd=budget,
            created_at=NOW - timedelta(minutes=minute),
        ),
    )


@pytest.mark.parametrize(
    ("play_type", "candidates"),
    [
        (PlayType.SINGLES, []),
        (PlayType.DOUBLES, []),
        (PlayType.DOUBLES, [candidate()]),
        (PlayType.DOUBLES, [candidate(), candidate(210, 211)]),
    ],
)
def test_no_group_when_too_few_candidates(play_type, candidates):
    assert find_group(CALLER, replace(REQUEST, play_type=play_type), candidates) is None


@pytest.mark.parametrize("rank", [6, 7, 8, 9, 10, 11, 12])
def test_rank_spread_includes_two_but_excludes_three(rank):
    suggestion = find_group(CALLER, REQUEST, [candidate(rank=rank)])
    assert (suggestion is not None) == (7 <= rank <= 11)


def test_rank_spread_applies_to_the_whole_group():
    request = replace(REQUEST, play_type=PlayType.DOUBLES)
    candidates = [candidate(rank=7), candidate(210, 211, rank=11), candidate(220, 221)]
    assert find_group(CALLER, request, candidates) is None


@pytest.mark.parametrize(
    ("caller_policy", "candidate_policy", "gender", "allowed"),
    [
        (GenderPolicy.ANY, GenderPolicy.ANY, Gender.FEMALE, True),
        (GenderPolicy.MALE_ONLY, GenderPolicy.ANY, Gender.FEMALE, False),
        (GenderPolicy.ANY, GenderPolicy.FEMALE_ONLY, Gender.FEMALE, False),
        (GenderPolicy.ANY, GenderPolicy.MALE_ONLY, Gender.FEMALE, False),
        (GenderPolicy.MALE_ONLY, GenderPolicy.MALE_ONLY, Gender.MALE, True),
        (GenderPolicy.ANY, GenderPolicy.ANY, Gender.UNSPECIFIED, False),
    ],
)
def test_each_request_policy_must_allow_every_member(
    caller_policy, candidate_policy, gender, allowed
):
    request = replace(REQUEST, gender_policy=caller_policy)
    suggestion = find_group(CALLER, request, [candidate(gender=gender, policy=candidate_policy)])
    assert (suggestion is not None) == allowed


@pytest.mark.parametrize("gender,fee", [(Gender.MALE, 60_000), (Gender.FEMALE, 40_000)])
@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_budget_uses_callers_fee_for_each_gender(gender, fee, difference):
    entrant = candidate(gender=gender, budget=fee + difference)
    # Candidates may propose different fees; the caller's proposal sets group fees.
    entrant = replace(
        entrant,
        request=replace(entrant.request, proposed_fee_male_vnd=1, proposed_fee_female_vnd=999_999),
    )
    suggestion = find_group(CALLER, REQUEST, [entrant])
    assert (suggestion is not None) == (difference >= 0)
    if suggestion is not None:
        assert suggestion.members[1].estimated_fee_vnd == fee


def test_callers_own_budget_is_checked():
    assert find_group(CALLER, replace(REQUEST, budget_max_vnd=59_999), [candidate()]) is None


def test_oldest_request_wins_before_lower_id():
    candidates = [candidate(200, 201), candidate(210, 211, minute=2)]
    suggestion = find_group(CALLER, REQUEST, candidates)
    assert suggestion is not None
    assert [member.id for member in suggestion.members] == [100, 211]


def test_equal_created_at_uses_request_id_instead_of_user_id():
    candidates = [candidate(210, 201), candidate(200, 211)]
    suggestion = find_group(CALLER, REQUEST, candidates)
    assert suggestion is not None
    assert [member.id for member in suggestion.members] == [100, 211]


def test_doubles_selects_first_valid_combination_without_changing_input():
    request = replace(REQUEST, play_type=PlayType.DOUBLES)
    candidates = [
        candidate(200, 201),
        candidate(210, 211, minute=2, rank=11),
        candidate(220, 221, minute=3, gender=Gender.FEMALE, budget=40_000),
        candidate(230, 231, minute=4, rank=10),
        candidate(240, 241, minute=5, rank=12),
    ]
    original_candidates = candidates.copy()
    suggestion = find_group(CALLER, request, candidates)
    assert suggestion is not None
    assert [member.id for member in suggestion.members] == [100, 231, 221, 211]
    assert candidates == original_candidates
    assert suggestion.capacity == 4
    assert suggestion.requires_confirmation is True
    assert suggestion.venue_id == request.venue_id
    assert suggestion.play_type == request.play_type
    assert (suggestion.starts_at, suggestion.ends_at) == (request.starts_at, request.ends_at)
    assert (suggestion.proposed_fee_male_vnd, suggestion.proposed_fee_female_vnd) == (
        60_000,
        40_000,
    )
    assert [member.estimated_fee_vnd for member in suggestion.members] == [
        60_000,
        60_000,
        40_000,
        60_000,
    ]


@pytest.mark.parametrize(
    "ineligible",
    [
        candidate(minute=2, rank=12),
        candidate(minute=2, gender=Gender.FEMALE, policy=GenderPolicy.FEMALE_ONLY),
        candidate(minute=2, budget=59_999),
    ],
    ids=["rank", "policy", "budget"],
)
def test_singles_skips_older_invalid_candidate_and_selects_next(ineligible):
    candidates = [candidate(210, 211), ineligible]
    original_candidates = candidates.copy()
    suggestion = find_group(CALLER, REQUEST, candidates)
    assert suggestion is not None
    assert [member.id for member in suggestion.members] == [100, 211]
    assert candidates == original_candidates


def test_female_only_group_accepts_female_caller_and_candidate():
    caller = replace(CALLER, gender=Gender.FEMALE)
    request = replace(REQUEST, gender_policy=GenderPolicy.FEMALE_ONLY, budget_max_vnd=40_000)
    entrant = candidate(gender=Gender.FEMALE, policy=GenderPolicy.FEMALE_ONLY, budget=40_000)
    suggestion = find_group(caller, request, [entrant])
    assert suggestion is not None
    assert suggestion.capacity == 2
    assert [member.id for member in suggestion.members] == [100, 201]
    assert all(member.gender == Gender.FEMALE for member in suggestion.members)
    assert [member.estimated_fee_vnd for member in suggestion.members] == [40_000, 40_000]


@pytest.mark.parametrize(
    ("caller_gender", "policy", "other_gender"),
    [
        (Gender.MALE, GenderPolicy.MALE_ONLY, Gender.FEMALE),
        (Gender.FEMALE, GenderPolicy.FEMALE_ONLY, Gender.MALE),
    ],
)
def test_doubles_candidate_policy_must_allow_other_candidates(caller_gender, policy, other_gender):
    caller = replace(CALLER, gender=caller_gender)
    request = replace(REQUEST, play_type=PlayType.DOUBLES)
    candidates = [
        candidate(gender=caller_gender, policy=policy),
        candidate(210, 211, gender=other_gender),
        candidate(220, 221, gender=caller_gender),
    ]
    # The restrictive candidate accepts the caller and itself, but not a teammate.
    assert find_group(caller, request, candidates) is None


def test_doubles_does_not_pool_member_budgets():
    request = replace(REQUEST, play_type=PlayType.DOUBLES)
    candidates = [
        candidate(budget=59_999),
        candidate(210, 211, gender=Gender.FEMALE, budget=40_001),
        candidate(220, 221),
    ]
    # Total budget covers all fees, but one member cannot afford their own fee.
    assert find_group(CALLER, request, candidates) is None
