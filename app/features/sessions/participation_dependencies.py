from datetime import datetime, timezone

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.participation_service import ParticipationService

_session_factory = create_session_factory(engine)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def provide_participation_service() -> ParticipationService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    # Callback chỉ lấy Session khi Service đã mở UoW; không mở transaction từ dependency.
    return ParticipationService(
        repository=SqlAlchemyParticipationRepository(lambda: uow.session),
        uow=uow,
        matching_writer=SqlAlchemyMatchingRequestWriter(lambda: uow.session),
        clock=SystemClock(),
    )
