from datetime import datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import aliased

from app.db.models import (
    MatchingRequestModel,
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.entities import compute_display_status
from app.domain.enums import (
    CloseReason,
    Gender,
    GenderPolicy,
    MatchingStatus,
    PlayType,
    SessionStatus,
)
from app.features.discovery.contracts import (
    CreateMatchingInput,
    MatchingCandidate,
    MatchingFilter,
    MatchingRequestRecord,
    Page,
    PlayerSummary,
    SessionFilter,
    SessionRecord,
    VenueFilter,
    VenueRecord,
)

CAPACITY = {PlayType.SINGLES: 2, PlayType.DOUBLES: 4}


def to_venue_record(m: VenueModel) -> VenueRecord:
    return VenueRecord(
        id=m.id,
        name=m.name,
        address=m.address,
        district_code=m.district_code,
        is_active=m.is_active,
    )


def to_player_summary(m: UserModel) -> PlayerSummary:
    return PlayerSummary(
        id=m.id, display_name=m.display_name, skill_level=m.skill_level, gender=m.gender
    )


def to_matching_record(m: MatchingRequestModel) -> MatchingRequestRecord:
    return MatchingRequestRecord(
        id=m.id,
        user_id=m.user_id,
        venue_id=m.venue_id,
        starts_at=m.starts_at,
        ends_at=m.ends_at,
        play_type=m.play_type,
        proposed_fee_male_vnd=m.proposed_fee_male_vnd,
        proposed_fee_female_vnd=m.proposed_fee_female_vnd,
        budget_max_vnd=m.budget_max_vnd,
        gender_policy=m.gender_policy,
        status=m.status,
        closed_reason=m.closed_reason,
        created_at=m.created_at,
        closed_at=m.closed_at,
    )


def to_session_record(
    session_m: SessionModel,
    venue_m: VenueModel,
    host_m: UserModel,
    accepted_count: int,
    now: datetime,
) -> SessionRecord:
    capacity = CAPACITY[PlayType(session_m.play_type)]
    remaining_capacity = capacity - accepted_count
    host = to_player_summary(host_m)
    venue = to_venue_record(venue_m)
    status = SessionStatus(session_m.status)
    display_status = compute_display_status(
        status,
        session_m.starts_at,
        session_m.ends_at,
        accepted_count=accepted_count,
        capacity=capacity,
        now=now,
    )

    gender_policy = GenderPolicy(session_m.gender_policy)
    return SessionRecord(
        id=session_m.id,
        host=host,
        venue=venue,
        title=session_m.title,
        notes=session_m.notes,
        starts_at=session_m.starts_at,
        ends_at=session_m.ends_at,
        play_type=session_m.play_type,
        fee_male_vnd=session_m.fee_male_vnd,
        fee_female_vnd=session_m.fee_female_vnd,
        min_level=session_m.min_level,
        max_level=session_m.max_level,
        gender_policy=gender_policy,
        status=status,
        capacity=capacity,
        accepted_count=accepted_count,
        remaining_capacity=remaining_capacity,
        display_status=display_status,
    )


class SqlAlchemyDiscoveryRepository:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def find_venues(self, filter: VenueFilter) -> Page[VenueRecord]:
        session = self._uow.session
        conditions = [VenueModel.is_active.is_(True)]
        if filter.district_code:
            conditions.append(VenueModel.district_code == filter.district_code)

        total = session.scalar(select(func.count()).select_from(VenueModel).where(*conditions)) or 0
        rows = (
            self._uow.session.execute(
                select(VenueModel)
                .where(*conditions)
                .order_by(VenueModel.id)
                .limit(filter.limit)
                .offset(filter.offset)
            )
            .scalars()
            .all()
        )
        return Page(
            items=[to_venue_record(r) for r in rows],
            total=total,
            limit=filter.limit,
            offset=filter.offset,
        )

    def find_sessions(self, filter: SessionFilter) -> Page[SessionRecord]:
        session = self._uow.session

        if filter.host_me and filter.host_user_id is None:
            return Page(
                items=[],
                total=0,
                limit=filter.limit,
                offset=filter.offset,
            )

        host = aliased(UserModel)
        accepted_count = (
            select(func.count())
            .where(
                ParticipationModel.session_id == SessionModel.id,
                ParticipationModel.status == "ACCEPTED",
            )
            .correlate(SessionModel)
            .scalar_subquery()
        )

        capacity = case(
            (SessionModel.play_type == PlayType.SINGLES.value, CAPACITY[PlayType.SINGLES]),
            else_=CAPACITY[PlayType.DOUBLES],
        )
        base = (
            select(
                SessionModel,
                VenueModel,
                host,
                accepted_count.label("accepted_count"),
            )
            .join(
                VenueModel,
                VenueModel.id == SessionModel.venue_id,
            )
            .join(
                host,
                host.id == SessionModel.host_user_id,
            )
        )

        conds = []

        if filter.only_listable:
            conds.extend(
                [
                    SessionModel.status == "OPEN",
                    SessionModel.starts_at > filter.now,
                    VenueModel.is_active.is_(True),
                ]
            )

        if filter.host_user_id is not None:
            conds.append(SessionModel.host_user_id == filter.host_user_id)

        if filter.district_code:
            conds.append(VenueModel.district_code == filter.district_code)

        if filter.venue_id is not None:
            conds.append(SessionModel.venue_id == filter.venue_id)

        if filter.play_type is not None:
            conds.append(SessionModel.play_type == filter.play_type.value)

        if filter.available_from is not None:
            conds.append(SessionModel.starts_at >= filter.available_from)

        if filter.available_to is not None:
            conds.append(SessionModel.ends_at <= filter.available_to)

        if filter.skill_level is not None:
            conds.extend(
                [
                    SessionModel.min_level <= filter.skill_level,
                    SessionModel.max_level >= filter.skill_level,
                ]
            )

        # Lọc theo giới tính
        if filter.gender is not None:
            if filter.gender == Gender.MALE:
                conds.append(SessionModel.gender_policy.in_(["ANY", "MALE_ONLY"]))
            elif filter.gender == Gender.FEMALE:
                conds.append(SessionModel.gender_policy.in_(["ANY", "FEMALE_ONLY"]))
            elif filter.gender == Gender.UNSPECIFIED:
                conds.append(SessionModel.gender_policy == "ANY")

        # Lọc theo mức phí tối đa
        if filter.max_fee_vnd is not None:
            if filter.gender == Gender.MALE:
                conds.append(SessionModel.fee_male_vnd <= filter.max_fee_vnd)
            elif filter.gender == Gender.FEMALE:
                conds.append(SessionModel.fee_female_vnd <= filter.max_fee_vnd)
            else:
                conds.extend(
                    [
                        SessionModel.fee_male_vnd <= filter.max_fee_vnd,
                        SessionModel.fee_female_vnd <= filter.max_fee_vnd,
                    ]
                )

        # Chỉ lấy kèo còn chỗ
        if filter.only_available:
            conds.append(accepted_count < capacity)

        # Đếm tổng số kèo thỏa mãn toàn bộ điều kiện
        filtered = base.where(*conds).subquery()

        total = session.scalar(select(func.count()).select_from(filtered)) or 0

        rows = session.execute(
            base.where(*conds)
            .order_by(
                SessionModel.starts_at,
                SessionModel.id,
            )
            .limit(filter.limit)
            .offset(filter.offset)
        ).all()

        items = [
            to_session_record(
                session_m=session_m,
                venue_m=venue_m,
                host_m=host_m,
                accepted_count=count,
                now=filter.now,
            )
            for session_m, venue_m, host_m, count in rows
        ]

        return Page(
            items=items,
            total=total,
            limit=filter.limit,
            offset=filter.offset,
        )


class SqlAlchemyMatchingRepository:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def get_venue(self, venue_id: int) -> VenueRecord | None:
        model = self._uow.session.get(VenueModel, venue_id)
        return to_venue_record(model) if model is not None else None

    def get_user(self, user_id: int) -> PlayerSummary | None:
        model = self._uow.session.get(UserModel, user_id)
        return to_player_summary(model) if model is not None else None

    def has_accepted_overlap(self, user_id: int, starts_at: datetime, ends_at: datetime) -> bool:
        overlap = (
            select(ParticipationModel.id)
            .join(SessionModel, SessionModel.id == ParticipationModel.session_id)
            .where(
                ParticipationModel.user_id == user_id,
                ParticipationModel.status == "ACCEPTED",
                SessionModel.starts_at < ends_at,
                SessionModel.ends_at > starts_at,
            )
            .exists()
        )
        return bool(self._uow.session.scalar(select(overlap)))

    def close_active_for_user(self, user_id: int, reason: CloseReason, closed_at: datetime) -> None:
        self._uow.session.execute(
            update(MatchingRequestModel)
            .where(
                MatchingRequestModel.user_id == user_id,
                MatchingRequestModel.status == MatchingStatus.ACTIVE.value,
            )
            .values(
                status=MatchingStatus.CLOSED.value, closed_reason=reason.value, closed_at=closed_at
            )
        )

    def create(
        self, data: CreateMatchingInput, user_id: int, created_at: datetime
    ) -> MatchingRequestRecord:
        model = MatchingRequestModel(
            user_id=user_id,
            venue_id=data.venue_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            play_type=data.play_type,
            proposed_fee_male_vnd=data.proposed_fee_male_vnd,
            proposed_fee_female_vnd=data.proposed_fee_female_vnd,
            budget_max_vnd=data.budget_max_vnd,
            gender_policy=data.gender_policy.value,
            status=MatchingStatus.ACTIVE.value,
            closed_reason=None,
            created_at=created_at,
            closed_at=None,
        )
        session = self._uow.session
        session.add(model)
        session.flush()

        return to_matching_record(model)

    def candidates(self, matching_filter: MatchingFilter) -> list[MatchingCandidate]:
        has_overlap = (
            select(ParticipationModel.id)
            .join(SessionModel, SessionModel.id == ParticipationModel.session_id)
            .where(
                ParticipationModel.user_id == UserModel.id,
                ParticipationModel.status == "ACCEPTED",
                SessionModel.starts_at < matching_filter.ends_at,
                SessionModel.ends_at > matching_filter.starts_at,
            )
            .correlate(UserModel)
            .exists()
        )

        rows = self._uow.session.execute(
            select(MatchingRequestModel, UserModel)
            .join(
                UserModel,
                UserModel.id == MatchingRequestModel.user_id,
            )
            .where(
                MatchingRequestModel.status == "ACTIVE",
                MatchingRequestModel.venue_id == matching_filter.venue_id,
                MatchingRequestModel.play_type == matching_filter.play_type,
                MatchingRequestModel.starts_at == matching_filter.starts_at,
                MatchingRequestModel.ends_at == matching_filter.ends_at,
                MatchingRequestModel.starts_at > matching_filter.now,
                MatchingRequestModel.user_id != matching_filter.exclude_user_id,
                UserModel.gender.in_((Gender.MALE.value, Gender.FEMALE.value)),
                ~has_overlap,
            )
            .order_by(
                MatchingRequestModel.created_at,
                MatchingRequestModel.id,
            )
        ).all()

        return [
            MatchingCandidate(request=to_matching_record(r), player=to_player_summary(u))
            for r, u in rows
        ]
