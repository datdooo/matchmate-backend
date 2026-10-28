from dataclasses import replace
from itertools import combinations

from app.domain.enums import CloseReason, Gender, GenderPolicy, PlayType
from app.domain.errors import DomainError
from app.domain.ports import Clock, UnitOfWork
from app.domain.time_rules import is_valid_time_window
from app.features.discovery.contracts import (
    CreateMatchingInput,
    DiscoveryRepository,
    MatchingFilter,
    MatchingRepository,
    MatchingRequestRecord,
    MatchingResult,
    MatchingSuggestion,
    Page,
    PlayerSummary,
    SessionFilter,
    SuggestedMember,
    VenueFilter,
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
    candidates: list[tuple[PlayerSummary, MatchingRequestRecord]],
) -> MatchingSuggestion | None:
    capacity = CAPACITY[caller_request.play_type]
    need = capacity - 1

    candidate_members = [(c.player, c.request) for c in candidates]
    candidate_members.sort(key=lambda m: (m[1].created_at, m[1].id))

    caller_member = (caller, caller_request)

    for combo in combinations(candidate_members, need):
        group = [caller_member, *combo]
        if group_is_valid(group, caller_request):
            return build_suggestion(group, caller_request, capacity)

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

class DiscoveryService:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        discovery_repo: DiscoveryRepository,
        matching_repo: MatchingRepository,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._discovery = discovery_repo
        self._matching = matching_repo

    def search_venues(self, filt: VenueFilter) -> Page:
        with self._uow.read():
            return self._discovery.find_venues(filt)

    def search_sessions(self, filt: SessionFilter, viewer_id: int | None) -> Page:
        if filt.host_me and viewer_id is None:
            raise DomainError(
            "UNAUTHORIZED",
            "Đăng nhập để xem các kèo của bạn.",
        )

        with self._uow.read():
            now = self._clock.now()

            if filt.host_me:
                filt = replace(
                    filt,
                    now=now,
                    host_user_id=viewer_id,
                    only_listable=False,
                    only_available=False,
                )
            else:
                filt = replace(filt, now=now, host_user_id=None)
            return self._discovery.find_sessions(filt)

    def create_matching_request(
        self, actor_user_id: int, data: CreateMatchingInput
    ) -> MatchingResult:

        with self._uow.write():
            now = self._clock.now()
            caller = self._matching.get_user(actor_user_id)

            if caller is None:
                raise DomainError("UNAUTHORIZED", "Tài khoản không tồn tại")

            if caller.gender not in (Gender.MALE, Gender.FEMALE):
                raise DomainError("PROFILE_INCOMPLETE", "Hồ sơ chưa có giới tính")
            
            venue = self._matching.get_venue(data.venue_id)
            if venue is None:
                raise DomainError("VENUE_NOT_FOUND", "Không tìm thấy sân")

            if not venue.is_active:
                raise DomainError("VENUE_INACTIVE", "Sân không hoạt động")

            if not is_valid_time_window(data.starts_at, data.ends_at, now):
                raise DomainError("INVALID_TIME_WINDOW", "Thời gian không hợp lệ")

            if not policy_allows(data.gender_policy, caller.gender):
                raise DomainError("ELIGIBILITY_MISMATCH", "Hồ sơ không đáp ứng policy giới tính")

            my_fee = fee_for(
                        caller.gender,
                        data.proposed_fee_male_vnd,
                        data.proposed_fee_female_vnd,
                    )
            if my_fee > data.budget_max_vnd:
                raise DomainError("VALIDATION_ERROR", "Phí đề xuất vượt ngân sách của bạn")

            if self._matching.has_accepted_overlap(
                actor_user_id, data.starts_at, data.ends_at
            ):
                raise DomainError("TIME_CONFLICT", "Đã có lịch ACCEPTED chồng giờ")

            self._matching.close_active_for_user(actor_user_id, CloseReason.REPLACED, now)

            created = self._matching.create(data, actor_user_id, now)

            candidates = self._matching.candidates(
                MatchingFilter(
                    venue_id=data.venue_id,
                    play_type=data.play_type,
                    starts_at=data.starts_at,
                    ends_at=data.ends_at,
                    exclude_user_id=actor_user_id,
                    now=now,
                )
            )
            suggestion = find_group(caller, created, candidates)

            self._uow.commit()
            return MatchingResult(request=created, suggestion=suggestion)