"""Regression cho DTO đọc từ SQLite thật khi tích hợp các feature."""

from datetime import datetime, timedelta, timezone

from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.enums import PlayType
from app.features.auth.contracts import DatabaseBusyError
from app.features.discovery.contracts import CreateMatchingInput, SessionFilter
from app.features.discovery.repository import (
    SqlAlchemyDiscoveryRepository,
    SqlAlchemyMatchingRepository,
)

NOW = datetime(2030, 11, 1, 10, tzinfo=timezone.utc)


def test_session_query_keeps_full_host_and_venue(db_session_factory, game_data):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    with uow.read():
        page = SqlAlchemyDiscoveryRepository(uow).find_sessions(SessionFilter(now=NOW))
    assert page.total == 2
    assert page.items[0].host.id == game_data["host"]
    assert page.items[0].host.display_name == "host"
    assert page.items[0].venue.id == game_data["venue"]
    assert page.items[0].venue.district_code == "CAU_GIAY"


def test_matching_create_returns_record_from_real_adapter(db_session_factory, game_data):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    with uow.write():
        record = SqlAlchemyMatchingRepository(uow).create(
            CreateMatchingInput(
                venue_id=game_data["venue"],
                starts_at=NOW + timedelta(days=1),
                ends_at=NOW + timedelta(days=1, hours=2),
                play_type=PlayType.DOUBLES,
                proposed_fee_male_vnd=60000,
                proposed_fee_female_vnd=40000,
                budget_max_vnd=80000,
            ),
            game_data["player"],
            NOW,
        )
        uow.commit()
    assert record.id > 0 and record.user_id == game_data["player"]
    assert record.status == "ACTIVE" and record.closed_at is None
