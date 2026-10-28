from datetime import datetime, timezone

import pytest

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth.contracts import DatabaseBusyError
from app.features.sessions import participation_dependencies
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.participation_service import ParticipationService
from app.main import app

NOW = datetime(2030, 11, 1, 10, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.value = NOW

    def now(self):
        return self.value


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def make_service(db_session_factory, clock):
    def build(factory=None, timer=None):
        uow = SqlAlchemyUnitOfWork(factory or db_session_factory, DatabaseBusyError)
        return ParticipationService(
            SqlAlchemyParticipationRepository(lambda: uow.session),
            uow,
            SqlAlchemyMatchingRequestWriter(lambda: uow.session),
            timer or clock,
        )

    return build


@pytest.fixture
def service(make_service):
    return make_service()


@pytest.fixture
def client(client, make_service):
    # Mở rộng client chung bằng Clock cố định cho các ca đúng ranh giới giờ bắt đầu.
    app.dependency_overrides[participation_dependencies.provide_participation_service] = (
        make_service
    )
    return client
