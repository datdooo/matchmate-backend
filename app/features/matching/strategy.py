"""Select the first valid group without database, HTTP, or clock access."""

from itertools import combinations

from app.domain.enums import Gender, GenderPolicy, PlayType
from app.features.matching.contracts import (
    MatchingCandidate,
    MatchingRequestRecord,
    MatchingSuggestion,
    PlayerSummary,
    SuggestedMember,
)

CAPACITY = {PlayType.SINGLES: 2, PlayType.DOUBLES: 4}
MAX_RANK_SPREAD = 2


def policy_allows(policy: GenderPolicy, gender: Gender) -> bool:
    if policy == GenderPolicy.ANY:
        return True
    if policy == GenderPolicy.MALE_ONLY:
        return gender == Gender.MALE
    return gender == Gender.FEMALE


def fee_for(gender: Gender, fee_male_vnd: int, fee_female_vnd: int) -> int:
    return fee_male_vnd if gender == Gender.MALE else fee_female_vnd


def group_is_valid(
    members: list[tuple[PlayerSummary, MatchingRequestRecord]],
    caller_request: MatchingRequestRecord,
) -> bool:
    if not members:
        return False

    users = [user for user, _ in members]

    for user in users:
        if user.gender not in (Gender.MALE, Gender.FEMALE):
            return False

    ranks = [user.skill_level for user in users]
    if max(ranks) - min(ranks) > MAX_RANK_SPREAD:
        return False

    requests = [request for _, request in members]
    for request in requests:
        for user in users:
            if not policy_allows(request.gender_policy, user.gender):
                return False

    for user, request in members:
        fee = fee_for(
            user.gender,
            caller_request.proposed_fee_male_vnd,
            caller_request.proposed_fee_female_vnd,
        )
        if fee > request.budget_max_vnd:
            return False

    return True


def find_group(
    caller: PlayerSummary,
    caller_request: MatchingRequestRecord,
    candidates: list[MatchingCandidate],
) -> MatchingSuggestion | None:
    capacity = CAPACITY[caller_request.play_type]
    required_candidates = capacity - 1

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (candidate.request.created_at, candidate.request.id),
    )
    candidate_members = [(candidate.player, candidate.request) for candidate in ordered_candidates]

    caller_member = (caller, caller_request)

    for candidate_group in combinations(candidate_members, required_candidates):
        group = [caller_member, *candidate_group]
        if group_is_valid(group, caller_request):
            return build_suggestion(
                group=group,
                caller_request=caller_request,
                capacity=capacity,
            )

    return None


def build_suggestion(
    group: list[tuple[PlayerSummary, MatchingRequestRecord]],
    caller_request: MatchingRequestRecord,
    capacity: int,
) -> MatchingSuggestion:
    members = [
        SuggestedMember(
            id=player.id,
            display_name=player.display_name,
            skill_level=player.skill_level,
            gender=player.gender,
            estimated_fee_vnd=fee_for(
                player.gender,
                caller_request.proposed_fee_male_vnd,
                caller_request.proposed_fee_female_vnd,
            ),
        )
        for player, _ in group
    ]
    return MatchingSuggestion(
        venue_id=caller_request.venue_id,
        play_type=caller_request.play_type,
        capacity=capacity,
        starts_at=caller_request.starts_at,
        ends_at=caller_request.ends_at,
        proposed_fee_male_vnd=caller_request.proposed_fee_male_vnd,
        proposed_fee_female_vnd=caller_request.proposed_fee_female_vnd,
        members=members,
        requires_confirmation=True,
    )
