from app.domain.entities import PlayerSummary
from app.domain.enums import CloseReason, Gender, skill_to_rank
from app.domain.errors import DomainError
from app.domain.ports import Clock, UnitOfWork
from app.domain.time_rules import is_valid_time_window
from app.features.auth.contracts import PlayerProfile, PlayerProfileReader, PlayerProfilesReader
from app.features.catalog.contracts import VenueStatusReader
from app.features.matching.contracts import (
    CreateMatchingInput,
    MatchingCandidate,
    MatchingFilter,
    MatchingRepository,
    MatchingResult,
    MatchingStrategy,
)
from app.features.matching.domain.strategy import fee_for, find_group, policy_allows


def to_player(profile: PlayerProfile) -> PlayerSummary:
    return PlayerSummary(
        profile.id, profile.display_name, skill_to_rank(profile.skill_level), profile.gender
    )


class MatchingService:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        matching_repo: MatchingRepository,
        profile_reader: PlayerProfileReader,
        profiles_reader: PlayerProfilesReader,
        venues: VenueStatusReader,
        strategy: MatchingStrategy = find_group,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._matching = matching_repo
        self._profile = profile_reader
        self._profiles = profiles_reader
        self._venues = venues
        self._strategy = strategy

    def create_matching_request(
        self, actor_user_id: int, data: CreateMatchingInput
    ) -> MatchingResult:
        with self._uow.write():
            now = self._clock.now()
            profile = self._profile.get_by_id(actor_user_id)
            if profile is None:
                raise DomainError("UNAUTHORIZED", "Tài khoản không tồn tại")
            if profile.gender not in (Gender.MALE, Gender.FEMALE):
                raise DomainError("PROFILE_INCOMPLETE", "Hồ sơ chưa có giới tính")
            caller = to_player(profile)
            active = self._venues.is_active(data.venue_id)
            if active is None:
                raise DomainError("VENUE_NOT_FOUND", "Không tìm thấy sân")
            if not active:
                raise DomainError("VENUE_INACTIVE", "Sân không hoạt động")
            if not is_valid_time_window(data.starts_at, data.ends_at, now):
                raise DomainError("INVALID_TIME_WINDOW", "Thời gian không hợp lệ")
            if not policy_allows(data.gender_policy, caller.gender):
                raise DomainError("ELIGIBILITY_MISMATCH", "Hồ sơ không đáp ứng policy giới tính")
            if (
                fee_for(caller.gender, data.proposed_fee_male_vnd, data.proposed_fee_female_vnd)
                > data.budget_max_vnd
            ):
                raise DomainError("VALIDATION_ERROR", "Phí đề xuất vượt ngân sách của bạn")
            if self._matching.has_accepted_overlap(actor_user_id, data.starts_at, data.ends_at):
                raise DomainError("TIME_CONFLICT", "Đã có lịch ACCEPTED chồng giờ")
            self._matching.close_active_for_user(actor_user_id, CloseReason.REPLACED, now)
            created = self._matching.create(data, actor_user_id, now)
            requests = self._matching.candidates(
                MatchingFilter(
                    venue_id=data.venue_id,
                    play_type=data.play_type,
                    starts_at=data.starts_at,
                    ends_at=data.ends_at,
                    exclude_user_id=actor_user_id,
                    now=now,
                )
            )
            profiles = self._profiles.get_by_ids([request.user_id for request in requests])
            candidates = [
                MatchingCandidate(request=request, player=to_player(candidate))
                for request in requests
                if (candidate := profiles.get(request.user_id)) is not None
                and candidate.gender in (Gender.MALE, Gender.FEMALE)
            ]
            suggestion = self._strategy(caller, created, candidates)
            self._uow.commit()
            return MatchingResult(request=created, suggestion=suggestion)
