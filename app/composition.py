"""Connect public ports to adapters. Feature use cases never select implementations."""

from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DatabaseBusyError
from app.domain.time_rules import SystemClock
from app.features.auth.infrastructure.player_profile_reader import SqlAlchemyPlayerProfileReader
from app.features.catalog.venue_reader import (
    SqlAlchemyVenueReader,
    SqlAlchemyVenueStatusReader,
)
from app.features.discovery.repository import SqlAlchemyDiscoveryRepository
from app.features.discovery.service import DiscoveryService
from app.features.matching.matching_request_writer import (
    SqlAlchemyMatchingRequestWriter,
)
from app.features.matching.repository import SqlAlchemyMatchingRepository
from app.features.matching.service import MatchingService
from app.features.matching.strategy import find_group
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.participation_service import ParticipationService
from app.features.sessions.session_detail_reader import SqlAlchemySessionDetailReader
from app.features.sessions.session_detail_service import SessionDetailService
from app.features.sessions.session_repository import SqlAlchemySessionRepository
from app.features.sessions.session_service import SessionService

_session_factory = create_session_factory(engine)


def provide_discovery_service() -> DiscoveryService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    return DiscoveryService(
        uow=uow,
        clock=SystemClock(),
        discovery_repo=SqlAlchemyDiscoveryRepository(uow),
    )


def provide_matching_service() -> MatchingService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    profiles = SqlAlchemyPlayerProfileReader(lambda: uow.session)
    return MatchingService(
        uow=uow,
        clock=SystemClock(),
        matching_repo=SqlAlchemyMatchingRepository(uow),
        profile_reader=profiles,
        profiles_reader=profiles,
        venues=SqlAlchemyVenueStatusReader(lambda: uow.session),
        strategy=find_group,
    )


def provide_participation_service() -> ParticipationService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    return ParticipationService(
        SqlAlchemyParticipationRepository(lambda: uow.session),
        uow,
        SqlAlchemyMatchingRequestWriter(lambda: uow.session),
        SystemClock(),
        SqlAlchemyPlayerProfileReader(lambda: uow.session),
    )


def provide_session_service() -> SessionService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    return SessionService(
        uow=uow,
        sessions=SqlAlchemySessionRepository(lambda: uow.session),
        details=_session_detail_reader(uow),
        users=SqlAlchemyPlayerProfileReader(lambda: uow.session),
        clock=SystemClock(),
        venues=SqlAlchemyVenueStatusReader(lambda: uow.session),
        matching_writer=SqlAlchemyMatchingRequestWriter(lambda: uow.session),
    )


def provide_session_detail_service() -> SessionDetailService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    return SessionDetailService(uow, _session_detail_reader(uow), SystemClock())


def _session_detail_reader(uow: SqlAlchemyUnitOfWork) -> SqlAlchemySessionDetailReader:
    venues = SqlAlchemyVenueReader(lambda: uow.session)
    return SqlAlchemySessionDetailReader(lambda: uow.session, venues)
