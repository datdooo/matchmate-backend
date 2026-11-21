from dataclasses import replace

from app.domain.enums import CloseReason, Gender
from app.domain.errors import DomainError
from app.domain.ports import Clock, UnitOfWork
from app.domain.time_rules import is_valid_time_window
from app.features.discovery.contracts import (
    CreateMatchingInput,
    DiscoveryRepository,
    MatchingFilter,
    MatchingRepository,
    MatchingResult,
    Page,
    SessionFilter,
    VenueFilter,
)
from app.features.matching.domain.strategy import fee_for, find_group, policy_allows


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

            if self._matching.has_accepted_overlap(actor_user_id, data.starts_at, data.ends_at):
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
