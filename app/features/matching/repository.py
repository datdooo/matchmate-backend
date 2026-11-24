from datetime import datetime

from sqlalchemy import select, update

from app.db.models import MatchingRequestModel, ParticipationModel, SessionModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.enums import CloseReason, MatchingStatus
from app.features.matching.contracts import (
    CreateMatchingInput,
    MatchingFilter,
    MatchingRequestRecord,
)


def to_matching_record(request_model: MatchingRequestModel) -> MatchingRequestRecord:
    return MatchingRequestRecord(
        id=request_model.id,
        user_id=request_model.user_id,
        venue_id=request_model.venue_id,
        starts_at=request_model.starts_at,
        ends_at=request_model.ends_at,
        play_type=request_model.play_type,
        proposed_fee_male_vnd=request_model.proposed_fee_male_vnd,
        proposed_fee_female_vnd=request_model.proposed_fee_female_vnd,
        budget_max_vnd=request_model.budget_max_vnd,
        gender_policy=request_model.gender_policy,
        status=request_model.status,
        closed_reason=request_model.closed_reason,
        created_at=request_model.created_at,
        closed_at=request_model.closed_at,
    )


class SqlAlchemyMatchingRepository:
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

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
        new_request = MatchingRequestModel(
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
        session.add(new_request)
        session.flush()

        return to_matching_record(new_request)

    def candidates(self, matching_filter: MatchingFilter) -> list[MatchingRequestRecord]:
        has_overlap = (
            select(ParticipationModel.id)
            .join(SessionModel, SessionModel.id == ParticipationModel.session_id)
            .where(
                ParticipationModel.user_id == MatchingRequestModel.user_id,
                ParticipationModel.status == "ACCEPTED",
                SessionModel.starts_at < matching_filter.ends_at,
                SessionModel.ends_at > matching_filter.starts_at,
            )
            .correlate(MatchingRequestModel)
            .exists()
        )
        requests = self._uow.session.scalars(
            select(MatchingRequestModel)
            .where(
                MatchingRequestModel.status == "ACTIVE",
                MatchingRequestModel.venue_id == matching_filter.venue_id,
                MatchingRequestModel.play_type == matching_filter.play_type,
                MatchingRequestModel.starts_at == matching_filter.starts_at,
                MatchingRequestModel.ends_at == matching_filter.ends_at,
                MatchingRequestModel.starts_at > matching_filter.now,
                MatchingRequestModel.user_id != matching_filter.exclude_user_id,
                ~has_overlap,
            )
            .order_by(MatchingRequestModel.created_at, MatchingRequestModel.id)
        )
        return [to_matching_record(request) for request in requests]
