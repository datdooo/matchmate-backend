from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

from app.db.models import (
    ParticipationModel,
    SessionModel,
    UserModel,
    VenueModel,
)
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.entities import compute_display_status
from app.domain.enums import (
    Gender,
    GenderPolicy,
    PlayType,
    SessionStatus,
)
from app.features.discovery.contracts import (
    Page,
    PlayerSummary,
    SessionFilter,
    SessionRecord,
    VenueFilter,
    VenueRecord,
)

CAPACITY = {PlayType.SINGLES: 2, PlayType.DOUBLES: 4}


def to_venue_record(venue_model: VenueModel) -> VenueRecord:
    return VenueRecord(
        id=venue_model.id,
        name=venue_model.name,
        address=venue_model.address,
        district_code=venue_model.district_code,
        is_active=venue_model.is_active,
    )


def to_session_record(
    session_model: SessionModel,
    venue_model: VenueModel,
    host: PlayerSummary,
    accepted_count: int,
    now: datetime,
) -> SessionRecord:
    capacity = CAPACITY[PlayType(session_model.play_type)]
    remaining_capacity = capacity - accepted_count
    venue = to_venue_record(venue_model)
    status = SessionStatus(session_model.status)
    display_status = compute_display_status(
        status,
        session_model.starts_at,
        session_model.ends_at,
        accepted_count=accepted_count,
        capacity=capacity,
        now=now,
    )

    gender_policy = GenderPolicy(session_model.gender_policy)
    return SessionRecord(
        id=session_model.id,
        host=host,
        venue=venue,
        title=session_model.title,
        notes=session_model.notes,
        starts_at=session_model.starts_at,
        ends_at=session_model.ends_at,
        play_type=session_model.play_type,
        fee_male_vnd=session_model.fee_male_vnd,
        fee_female_vnd=session_model.fee_female_vnd,
        min_level=session_model.min_level,
        max_level=session_model.max_level,
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
            items=[to_venue_record(venue_model) for venue_model in rows],
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
        base_query = (
            select(
                SessionModel,
                VenueModel,
                host.id,
                host.display_name,
                host.skill_level,
                host.gender,
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

        conditions = []

        if filter.only_listable:
            conditions.extend(
                [
                    SessionModel.status == "OPEN",
                    SessionModel.starts_at > filter.now,
                    VenueModel.is_active.is_(True),
                ]
            )

        if filter.host_user_id is not None:
            conditions.append(SessionModel.host_user_id == filter.host_user_id)

        if filter.district_code:
            conditions.append(VenueModel.district_code == filter.district_code)

        if filter.venue_id is not None:
            conditions.append(SessionModel.venue_id == filter.venue_id)

        if filter.play_type is not None:
            conditions.append(SessionModel.play_type == filter.play_type.value)

        if filter.available_from is not None:
            conditions.append(SessionModel.starts_at >= filter.available_from)

        if filter.available_to is not None:
            conditions.append(SessionModel.ends_at <= filter.available_to)

        if filter.skill_level is not None:
            conditions.extend(
                [
                    SessionModel.min_level <= filter.skill_level,
                    SessionModel.max_level >= filter.skill_level,
                ]
            )

        # Lọc theo giới tính
        if filter.gender is not None:
            if filter.gender == Gender.MALE:
                conditions.append(SessionModel.gender_policy.in_(["ANY", "MALE_ONLY"]))
            elif filter.gender == Gender.FEMALE:
                conditions.append(SessionModel.gender_policy.in_(["ANY", "FEMALE_ONLY"]))
            elif filter.gender == Gender.UNSPECIFIED:
                conditions.append(SessionModel.gender_policy == "ANY")

        # Lọc theo mức phí tối đa
        if filter.max_fee_vnd is not None:
            if filter.gender == Gender.MALE:
                conditions.append(SessionModel.fee_male_vnd <= filter.max_fee_vnd)
            elif filter.gender == Gender.FEMALE:
                conditions.append(SessionModel.fee_female_vnd <= filter.max_fee_vnd)
            else:
                conditions.extend(
                    [
                        SessionModel.fee_male_vnd <= filter.max_fee_vnd,
                        SessionModel.fee_female_vnd <= filter.max_fee_vnd,
                    ]
                )

        # Chỉ lấy kèo còn chỗ
        if filter.only_available:
            conditions.append(accepted_count < capacity)

        # Đếm tổng số kèo thỏa mãn toàn bộ điều kiện
        filtered_query = base_query.where(*conditions).subquery()

        total = session.scalar(select(func.count()).select_from(filtered_query)) or 0

        rows = session.execute(
            base_query.where(*conditions)
            .order_by(
                SessionModel.starts_at,
                SessionModel.id,
            )
            .limit(filter.limit)
            .offset(filter.offset)
        ).all()

        items = []
        for (
            session_model,
            venue_model,
            host_id,
            host_name,
            host_rank,
            host_gender,
            count,
        ) in rows:
            host_profile = PlayerSummary(
                id=host_id,
                display_name=host_name,
                skill_level=host_rank,
                gender=Gender(host_gender),
            )
            record = to_session_record(
                session_model=session_model,
                venue_model=venue_model,
                host=host_profile,
                accepted_count=count,
                now=filter.now,
            )
            items.append(record)

        return Page(
            items=items,
            total=total,
            limit=filter.limit,
            offset=filter.offset,
        )
