from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.domain.errors import DomainError
from app.domain.ports import MatchingRequestWriter
from app.features.sessions.participation_contracts import ParticipationRepository
from app.features.sessions.participation_service import ParticipationService


def test_missing_session_rolls_back_before_any_mutation():
    events = []

    class FakeUow:
        @contextmanager
        def write(self):
            events.append("lock")
            try:
                yield self
            finally:
                events.append("rollback")

        def commit(self):
            raise AssertionError("Không commit khi kèo không tồn tại")

    def now():
        events.append("clock")
        return datetime(2030, 11, 1, tzinfo=timezone.utc)

    repository = Mock(spec=ParticipationRepository)
    repository.get_session.side_effect = lambda _id: events.append("lookup")
    service = ParticipationService(
        repository, FakeUow(), Mock(spec=MatchingRequestWriter), SimpleNamespace(now=now)
    )
    with pytest.raises(DomainError) as caught:
        service.join(1, 999)
    assert caught.value.code == "SESSION_NOT_FOUND"
    assert events == ["lock", "clock", "lookup", "rollback"]
    repository.create.assert_not_called()
