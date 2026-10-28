"""Luật xin, duyệt và rút lượt; mọi quyết định ghi nằm trong một UoW."""

from datetime import datetime
from typing import Literal

from app.domain.entities import Session
from app.domain.enums import Gender, GenderPolicy, ParticipationStatus, SessionStatus, skill_to_rank
from app.domain.errors import DomainError
from app.domain.ports import Clock, MatchingRequestWriter, UnitOfWork
from app.features.auth.contracts import User
from app.features.sessions.participation_contracts import (
    CreateParticipationInput,
    ParticipationDetail,
    ParticipationRepository,
)


class ParticipationService:
    def __init__(
        self,
        repository: ParticipationRepository,
        uow: UnitOfWork,
        matching_writer: MatchingRequestWriter,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.uow = uow
        self.matching_writer = matching_writer
        self.clock = clock

    def join(self, actor_user_id: int, session_id: int) -> ParticipationDetail:
        with self.uow.write():
            # BEGIN IMMEDIATE đã thành công. Không dùng thời gian cũ trước khi chờ khóa.
            now = self.clock.now()
            game = self._session(session_id)
            self._require_open(game, now)
            self._require_capacity(game)
            user = self._eligible_user(actor_user_id, game)
            if self.repository.has_active(actor_user_id, session_id):
                raise DomainError(
                    "PARTICIPATION_ALREADY_EXISTS", "Đã có lượt tham gia đang hoạt động"
                )
            if self.repository.has_overlap(actor_user_id, game.starts_at, game.ends_at):
                raise DomainError("TIME_CONFLICT", "Đã có lịch chơi được xác nhận chồng giờ")

            fee = game.fee_male_vnd if user.gender == Gender.MALE else game.fee_female_vnd
            part = self.repository.create(
                CreateParticipationInput(
                    user_id=actor_user_id,
                    session_id=session_id,
                    gender_at_join=user.gender,
                    quoted_fee_vnd=fee,
                ),
                now,
            )
            return self._finish(part.id, actor_user_id, now)

    def decide(
        self, actor_user_id: int, participation_id: int, decision: Literal["APPROVE", "REJECT"]
    ) -> ParticipationDetail:
        if decision not in ("APPROVE", "REJECT"):
            raise DomainError("VALIDATION_ERROR", "Quyết định phải là APPROVE hoặc REJECT")
        with self.uow.write():
            now = self.clock.now()
            part = self.repository.get_by_id(participation_id)
            if part is None:
                raise DomainError("PARTICIPATION_NOT_FOUND", "Không tìm thấy lượt tham gia")
            game = self._session(part.session_id)
            if actor_user_id != game.host_user_id:
                raise DomainError("FORBIDDEN", "Chỉ chủ kèo được quyết định yêu cầu")
            if part.status != ParticipationStatus.PENDING:
                raise DomainError("INVALID_STATE", "Chỉ quyết định yêu cầu đang PENDING")
            self._require_open(game, now)

            if decision == "APPROVE":
                # Kiểm lại hồ sơ hiện tại; snapshot lúc xin tham gia vẫn giữ nguyên.
                self._eligible_user(part.user_id, game)
                self._require_capacity(game)
                if self.repository.has_overlap(part.user_id, game.starts_at, game.ends_at):
                    raise DomainError("TIME_CONFLICT", "Người chơi đã có lịch chồng giờ")
                target = ParticipationStatus.ACCEPTED
            else:
                # Từ chối không phụ thuộc chỗ còn lại hay điều kiện tuyển người.
                target = ParticipationStatus.REJECTED

            self.repository.set_status(part.id, target, now)
            if target == ParticipationStatus.ACCEPTED:
                self.matching_writer.close_overlapping(
                    part.user_id,
                    game.starts_at,
                    game.ends_at,
                    now,
                )
            return self._finish(part.id, actor_user_id, now)

    def withdraw(self, actor_user_id: int, participation_id: int) -> ParticipationDetail:
        with self.uow.write():
            now = self.clock.now()
            part = self.repository.get_by_id(participation_id)
            if part is None:
                raise DomainError("PARTICIPATION_NOT_FOUND", "Không tìm thấy lượt tham gia")
            game = self._session(part.session_id)
            if actor_user_id != part.user_id:
                raise DomainError("FORBIDDEN", "Chỉ được rút lượt của mình")
            if actor_user_id == game.host_user_id:
                raise DomainError("HOST_PARTICIPATION_REQUIRED", "Chủ kèo phải hủy kèo để rút")

            # DELETE lặp trả bản cũ trước kiểm giờ; không đổi timestamp lần hai.
            if part.status == ParticipationStatus.CANCELLED:
                return self._finish(part.id, actor_user_id, now)
            if part.status not in (ParticipationStatus.PENDING, ParticipationStatus.ACCEPTED):
                raise DomainError("INVALID_STATE", "Lượt này không thể rút")
            self._require_open(game, now)
            self.repository.set_status(part.id, ParticipationStatus.CANCELLED, now)
            # Matching đã đóng không mở lại khi người chơi rút lượt.
            return self._finish(part.id, actor_user_id, now)

    def _session(self, session_id: int) -> Session:
        game = self.repository.get_session(session_id)
        if game is None:
            raise DomainError("SESSION_NOT_FOUND", "Không tìm thấy kèo")
        return game

    @staticmethod
    def _require_open(game: Session, now: datetime) -> None:
        if game.status == SessionStatus.CANCELLED:
            raise DomainError("SESSION_CANCELLED", "Kèo đã hủy")
        if now >= game.starts_at:
            raise DomainError("SESSION_ALREADY_STARTED", "Kèo đã bắt đầu")

    def _require_capacity(self, game: Session) -> None:
        if self.repository.count_accepted(game.id) >= game.capacity:
            raise DomainError("SESSION_FULL", "Kèo không còn chỗ để xác nhận")

    def _eligible_user(self, user_id: int, game: Session) -> User:
        user = self.repository.get_user(user_id)
        if user is None:
            raise DomainError("UNAUTHORIZED", "Tài khoản không tồn tại")
        if user.gender not in (Gender.MALE, Gender.FEMALE):
            raise DomainError("PROFILE_INCOMPLETE", "Cần khai giới tính để xác định phí")
        policy_matches = (
            game.gender_policy == GenderPolicy.ANY
            or game.gender_policy.value == f"{user.gender.value}_ONLY"
        )
        if (
            not policy_matches
            or not game.min_level <= skill_to_rank(user.skill_level) <= game.max_level
        ):
            raise DomainError("ELIGIBILITY_MISMATCH", "Hồ sơ không đáp ứng điều kiện của kèo")
        return user

    def _finish(
        self, participation_id: int, actor_user_id: int, now: datetime
    ) -> ParticipationDetail:
        # Đọc response trên cùng snapshot, sau flush và trước commit.
        detail = self.repository.detail(participation_id, actor_user_id, now)
        self.uow.commit()
        return detail
