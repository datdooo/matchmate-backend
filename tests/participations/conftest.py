from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.matching_request_writer import SqlAlchemyMatchingRequestWriter
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.features.auth import dependencies as auth_dependencies
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.tokens import JwtTokenIssuer
from app.features.sessions import participation_dependencies, session_router
from app.features.sessions.participation_repository import SqlAlchemyParticipationRepository
from app.features.sessions.participation_service import ParticipationService
from app.main import app

NOW = datetime(2030, 11, 1, 10, tzinfo=timezone.utc)
TEST_SECRET = "participation-tests-only-secret-32-bytes"


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
def client(monkeypatch, db_session_factory, make_service):
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setattr(auth_dependencies, "_session_factory", db_session_factory)
    monkeypatch.setattr(session_router, "_session_factory", db_session_factory)
    saved = app.dependency_overrides.copy()
    app.dependency_overrides[participation_dependencies.provide_participation_service] = (
        make_service
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


@pytest.fixture
def auth_headers():
    def headers(user_id):
        token = JwtTokenIssuer(TEST_SECRET, ttl_seconds=3600).issue(user_id)
        return {"Authorization": f"Bearer {token.access_token}"}

    return headers
