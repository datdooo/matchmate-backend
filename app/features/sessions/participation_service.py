"""Pure participation business rules for FR-08, FR-09 and FR-10."""

from __future__ import annotations

from datetime import datetime

from app.domain.ports import Clock
from app.domain.time_rules import ensure_utc_aware
from app.features.sessions.participation_contracts import (
    LEVEL_NAME_BY_RANK,
    CreateParticipationInput,
    Decision,
    DisplayStatus,
    Gender,
    GenderPolicy,
    Participation,
    ParticipationDetail,
    ParticipationError,
    ParticipationStatus,
    ParticipationTransaction,
    ParticipationUnitOfWorkFactory,
    PlayerSummary,
    SessionRecord,
    SessionStatus,
    SessionSummary,
    UserProfile,
    VenueView,
)


class ParticipationService:
    """Coordinate participation rules through ports only."""

    def __init__(self, uow: ParticipationUnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def join(self, actor_user_id: int, session_id: int) -> ParticipationDetail:
        with self._uow.write() as tx:
            now = ensure_utc_aware(self._clock.now())
            session = self._require_session(tx, session_id)
            self._require_open_future_session(session, now)
            user = self._require_profile(tx, actor_user_id)

            if tx.participations.has_active(actor_user_id, session_id):
                raise ParticipationError(
                    "PARTICIPATION_ALREADY_EXISTS",
                    "Người chơi đã có lượt hoạt động trong kèo này",
                    {"session_id": session_id},
                )

            accepted_count = tx.participations.count_accepted(session_id)
            if accepted_count >= session.capacity:
                raise ParticipationError(
                    "SESSION_FULL",
                    "Kèo không còn chỗ để gửi yêu cầu",
                    {"session_id": session_id},
                )

            self._require_eligible(user, session)
            if tx.participations.has_overlap(
                actor_user_id,
                session.starts_at,
                session.ends_at,
                exclude_session_id=session.id,
            ):
                raise ParticipationError(
                    "TIME_CONFLICT",
                    "Người chơi đã có lịch ACCEPTED chồng giờ",
                    {"session_id": session_id},
                )

            quoted_fee = self._quoted_fee(user, session)
            participation = tx.participations.create(
                CreateParticipationInput(
                    user_id=actor_user_id,
                    session_id=session_id,
                    status=ParticipationStatus.PENDING,
                    gender_at_join=user.gender,
                    quoted_fee_vnd=quoted_fee,
                ),
                now,
            )
            detail = self._build_detail(tx, participation, actor_user_id, now)
            tx.commit()
            return detail

    def decide(
        self,
        actor_user_id: int,
        participation_id: int,
        decision: Decision | str,
    ) -> ParticipationDetail:
        try:
            parsed_decision = Decision(decision)
        except ValueError as exc:
            raise ParticipationError(
                "VALIDATION_ERROR",
                "decision phải là APPROVE hoặc REJECT",
                {"field": "decision"},
            ) from exc

        with self._uow.write() as tx:
            now = ensure_utc_aware(self._clock.now())
            participation = self._require_participation(tx, participation_id)
            session = self._require_session(tx, participation.session_id)

            if session.host_user_id != actor_user_id:
                raise ParticipationError(
                    "FORBIDDEN",
                    "Chỉ chủ kèo được quyết định yêu cầu tham gia",
                    {"participation_id": participation_id},
                )
            if participation.status != ParticipationStatus.PENDING:
                raise ParticipationError(
                    "INVALID_STATE",
                    "Chỉ lượt PENDING mới có thể được quyết định",
                    {"participation_id": participation_id},
                )

            self._require_open_future_session(session, now)

            if parsed_decision is Decision.APPROVE:
                user = self._require_profile(tx, participation.user_id)
                self._require_eligible(user, session)

                accepted_count = tx.participations.count_accepted(session.id)
                if accepted_count >= session.capacity:
                    raise ParticipationError(
                        "SESSION_FULL",
                        "Kèo không còn chỗ để xác nhận",
                        {"session_id": session.id},
                    )
                if tx.participations.has_overlap(
                    participation.user_id,
                    session.starts_at,
                    session.ends_at,
                    exclude_session_id=session.id,
                ):
                    raise ParticipationError(
                        "TIME_CONFLICT",
                        "Người chơi đã có lịch ACCEPTED chồng giờ",
                        {"session_id": session.id},
                    )

                participation = tx.participations.set_status(
                    participation.id,
                    ParticipationStatus.ACCEPTED,
                    now,
                )
                tx.matching.close_overlapping(
                    participation.user_id,
                    session.starts_at,
                    session.ends_at,
                    now,
                )
            else:
                participation = tx.participations.set_status(
                    participation.id,
                    ParticipationStatus.REJECTED,
                    now,
                )

            detail = self._build_detail(tx, participation, actor_user_id, now)
            tx.commit()
            return detail

    def cancel(self, actor_user_id: int, participation_id: int) -> ParticipationDetail:
        with self._uow.write() as tx:
            now = ensure_utc_aware(self._clock.now())
            participation = self._require_participation(tx, participation_id)
            session = self._require_session(tx, participation.session_id)

            if participation.user_id != actor_user_id:
                raise ParticipationError(
                    "FORBIDDEN",
                    "Chỉ chủ lượt mới được rút lượt tham gia",
                    {"participation_id": participation_id},
                )

            if participation.status == ParticipationStatus.CANCELLED:
                detail = self._build_detail(tx, participation, actor_user_id, now)
                tx.commit()
                return detail

            if session.host_user_id == actor_user_id:
                raise ParticipationError(
                    "HOST_PARTICIPATION_REQUIRED",
                    "Chủ kèo phải hủy kèo thay vì rút lượt của mình",
                    {"session_id": session.id},
                )

            if now >= session.starts_at:
                raise ParticipationError(
                    "SESSION_ALREADY_STARTED",
                    "Kèo đã bắt đầu",
                    {"session_id": session.id},
                )
            if participation.status not in (
                ParticipationStatus.PENDING,
                ParticipationStatus.ACCEPTED,
            ):
                raise ParticipationError(
                    "INVALID_STATE",
                    "Trạng thái lượt không cho phép rút",
                    {"participation_id": participation.id},
                )

            participation = tx.participations.set_status(
                participation.id,
                ParticipationStatus.CANCELLED,
                now,
            )
            detail = self._build_detail(tx, participation, actor_user_id, now)
            tx.commit()
            return detail

    @staticmethod
    def _require_session(tx: ParticipationTransaction, session_id: int) -> SessionRecord:
        session = tx.sessions.get_by_id(session_id)
        if session is None:
            raise ParticipationError(
                "SESSION_NOT_FOUND",
                "Không tìm thấy kèo",
                {"session_id": session_id},
            )
        return session

    @staticmethod
    def _require_participation(
        tx: ParticipationTransaction,
        participation_id: int,
    ) -> Participation:
        participation = tx.participations.get_by_id(participation_id)
        if participation is None:
            raise ParticipationError(
                "PARTICIPATION_NOT_FOUND",
                "Không tìm thấy lượt tham gia",
                {"participation_id": participation_id},
            )
        return participation

    @staticmethod
    def _require_open_future_session(session: SessionRecord, now: datetime) -> None:
        if session.status == SessionStatus.CANCELLED:
            raise ParticipationError(
                "SESSION_CANCELLED",
                "Kèo đã bị hủy",
                {"session_id": session.id},
            )
        if now >= session.starts_at:
            raise ParticipationError(
                "SESSION_ALREADY_STARTED",
                "Kèo đã bắt đầu",
                {"session_id": session.id},
            )

    @staticmethod
    def _require_profile(tx: ParticipationTransaction, user_id: int) -> UserProfile:
        user = tx.users.get_by_id(user_id)
        if user is None:
            raise ParticipationError(
                "PROFILE_INCOMPLETE",
                "Hồ sơ người chơi không đầy đủ",
                {"user_id": user_id},
            )
        if user.gender not in (Gender.MALE, Gender.FEMALE):
            raise ParticipationError(
                "PROFILE_INCOMPLETE",
                "Hồ sơ cần giới tính MALE hoặc FEMALE",
                {"user_id": user_id},
            )
        if user.skill_level not in LEVEL_NAME_BY_RANK:
            raise ParticipationError(
                "PROFILE_INCOMPLETE",
                "Hồ sơ có trình độ không hợp lệ",
                {"user_id": user_id},
            )
        return user

    @staticmethod
    def _require_eligible(user: UserProfile, session: SessionRecord) -> None:
        level_ok = session.min_level <= user.skill_level <= session.max_level
        policy_ok = (
            session.gender_policy == GenderPolicy.ANY
            or (session.gender_policy == GenderPolicy.MALE_ONLY and user.gender == Gender.MALE)
            or (session.gender_policy == GenderPolicy.FEMALE_ONLY and user.gender == Gender.FEMALE)
        )
        if not level_ok or not policy_ok:
            raise ParticipationError(
                "ELIGIBILITY_MISMATCH",
                "Hồ sơ người chơi không đáp ứng điều kiện tuyển",
                {"session_id": session.id},
            )

    @staticmethod
    def _quoted_fee(user: UserProfile, session: SessionRecord) -> int:
        if user.gender == Gender.MALE:
            return session.fee_male_vnd
        return session.fee_female_vnd

    def _build_detail(
        self,
        tx: ParticipationTransaction,
        participation: Participation,
        actor_user_id: int,
        now: datetime,
    ) -> ParticipationDetail:
        session = self._require_session(tx, participation.session_id)
        user = tx.users.get_by_id(participation.user_id)
        if user is None:
            raise ParticipationError(
                "INTERNAL_ERROR",
                "Dữ liệu người chơi của lượt tham gia không còn tồn tại",
                {"user_id": participation.user_id},
            )
        accepted_count = tx.participations.count_accepted(session.id)
        session_summary = self._session_summary(session, accepted_count, now)

        is_owner = participation.user_id == actor_user_id
        is_host_participation = participation.user_id == session.host_user_id
        can_cancel = (
            is_owner
            and not is_host_participation
            and participation.status in (ParticipationStatus.PENDING, ParticipationStatus.ACCEPTED)
            and session.status == SessionStatus.OPEN
            and now < session.starts_at
        )
        can_decide = (
            actor_user_id == session.host_user_id
            and participation.status == ParticipationStatus.PENDING
            and session.status == SessionStatus.OPEN
            and now < session.starts_at
        )
        player = self._player_summary(user)
        return ParticipationDetail(
            id=participation.id,
            user_id=participation.user_id,
            session_id=participation.session_id,
            player=player,
            status=participation.status,
            created_at=participation.created_at,
            decided_at=participation.decided_at,
            cancelled_at=participation.cancelled_at,
            can_cancel=can_cancel,
            can_decide=can_decide,
            gender_at_join=participation.gender_at_join,
            quoted_fee_vnd=participation.quoted_fee_vnd,
            session=session_summary,
        )

    def _session_summary(
        self,
        session: SessionRecord,
        accepted_count: int,
        now: datetime,
    ) -> SessionSummary:
        remaining = max(0, session.capacity - accepted_count)
        if session.status == SessionStatus.CANCELLED:
            display_status = DisplayStatus.CANCELLED
        elif now >= session.ends_at:
            display_status = DisplayStatus.ENDED
        elif now >= session.starts_at:
            display_status = DisplayStatus.STARTED
        elif accepted_count >= session.capacity:
            display_status = DisplayStatus.FULL
        else:
            display_status = DisplayStatus.AVAILABLE

        return SessionSummary(
            id=session.id,
            title=session.title,
            host=self._player_summary(session.host),
            venue=VenueView(
                id=session.venue.id,
                name=session.venue.name,
                address=session.venue.address,
                district_code=session.venue.district_code,
                latitude=session.venue.latitude,
                longitude=session.venue.longitude,
                distance_km=None,
            ),
            starts_at=session.starts_at,
            ends_at=session.ends_at,
            play_type=session.play_type,
            capacity=session.capacity,
            fee_male_vnd=session.fee_male_vnd,
            fee_female_vnd=session.fee_female_vnd,
            min_level=LEVEL_NAME_BY_RANK[session.min_level],
            max_level=LEVEL_NAME_BY_RANK[session.max_level],
            gender_policy=session.gender_policy,
            status=session.status,
            display_status=display_status,
            accepted_count=accepted_count,
            remaining_capacity=remaining,
        )

    @staticmethod
    def _player_summary(user: UserProfile) -> PlayerSummary:
        return PlayerSummary(
            id=user.id,
            display_name=user.display_name,
            skill_level=LEVEL_NAME_BY_RANK[user.skill_level],
            gender=user.gender,
        )
