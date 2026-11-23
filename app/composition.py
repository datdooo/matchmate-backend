"""Connect public ports to adapters. Feature use cases never select implementations."""

from app.db.session import create_session_factory, engine
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DatabaseBusyError
from app.domain.time_rules import SystemClock
from app.features.auth.infrastructure.player_profile_reader import SqlAlchemyPlayerProfileReader
from app.features.catalog.infrastructure.venue_reader import (
    SqlAlchemyVenueReader,
    SqlAlchemyVenueStatusReader,
)
from app.features.discovery.repository import SqlAlchemyDiscoveryRepository
from app.features.discovery.service import DiscoveryService
from app.features.matching.domain.strategy import find_group
from app.features.matching.infrastructure.matching_request_writer import (
    SqlAlchemyMatchingRequestWriter,
)
from app.features.matching.infrastructure.repository import SqlAlchemyMatchingRepository
from app.features.matching.service import MatchingService
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.participation_service import ParticipationService
from app.features.sessions.session_repository import SqlAlchemySessionRepository
from app.features.sessions.session_service import SessionService

_session_factory = create_session_factory(engine)


def provide_discovery_service() -> DiscoveryService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    return DiscoveryService(uow, SystemClock(), SqlAlchemyDiscoveryRepository(uow))


def provide_matching_service() -> MatchingService:
    uow = SqlAlchemyUnitOfWork(_session_factory, DatabaseBusyError)
    profiles = SqlAlchemyPlayerProfileReader(lambda: uow.session)
    return MatchingService(
        uow,
        SystemClock(),
        SqlAlchemyMatchingRepository(uow),
        profiles,
        profiles,
        SqlAlchemyVenueStatusReader(lambda: uow.session),
        find_group,
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
    venues = SqlAlchemyVenueReader(lambda: uow.session)
    return SessionService(
        uow=uow,
        sessions=SqlAlchemySessionRepository(lambda: uow.session, venues),
        users=SqlAlchemyPlayerProfileReader(lambda: uow.session),
        clock=SystemClock(),
        venues=SqlAlchemyVenueStatusReader(lambda: uow.session),
        matching_writer=SqlAlchemyMatchingRequestWriter(lambda: uow.session),
    )
