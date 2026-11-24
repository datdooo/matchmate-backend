import sqlite3

import pytest
from sqlalchemy import event, update
from sqlalchemy.exc import OperationalError

from app.db.models import VenueModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DatabaseBusyError
from app.features.catalog.contracts import VenueSummary
from app.features.catalog.venue_reader import (
    SqlAlchemyVenueReader,
    SqlAlchemyVenueStatusReader,
)


@pytest.fixture
def venues(db_session_factory):
    with db_session_factory.begin() as session:
        session.add_all(
            [
                VenueModel(id=1, name="Sân active", address="Địa chỉ 1", district_code="CAU_GIAY"),
                VenueModel(
                    id=2,
                    name="Sân inactive",
                    address="Địa chỉ 2",
                    district_code="DONG_DA",
                    is_active=False,
                ),
            ]
        )


@pytest.mark.parametrize("venue_id,expected", [(1, True), (2, False), (999, None)])
def test_status_distinguishes_active_inactive_and_missing(
    db_session_factory, venues, venue_id, expected
):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyVenueStatusReader(lambda: uow.session)
    with uow.read():
        assert reader.is_active(venue_id) is expected


@pytest.mark.parametrize(
    ("venue_id", "expected"),
    [
        (1, VenueSummary(1, "Sân active", "Địa chỉ 1", "CAU_GIAY", True)),
        (2, VenueSummary(2, "Sân inactive", "Địa chỉ 2", "DONG_DA", False)),
        (999, None),
    ],
    ids=["active", "inactive", "missing"],
)
def test_summary_returns_dto_or_none_after_transaction_ends(
    db_session_factory, venues, venue_id, expected
):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyVenueReader(lambda: uow.session)
    with uow.read():
        summary = reader.get_by_id(venue_id)
    assert summary == expected


def test_empty_batch_does_not_access_session():
    def unexpected_session():
        pytest.fail("An empty batch must not access the database")

    assert SqlAlchemyVenueReader(unexpected_session).get_by_ids([]) == {}


def test_large_batch_deduplicates_ids_and_limits_query_parameters(db_session_factory, db_engine):
    with db_session_factory.begin() as session:
        session.add_all(
            VenueModel(
                id=venue_id,
                name=f"Sân {venue_id}",
                address="Địa chỉ",
                district_code="CAU_GIAY",
                is_active=venue_id != 2,
            )
            for venue_id in range(1, 1002)
        )

    queries = []

    def capture_query(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append((parameters, list(context.compiled.statement.selected_columns.keys())))

    event.listen(db_engine, "before_cursor_execute", capture_query)
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyVenueReader(lambda: uow.session)
    try:
        with uow.read():
            summaries = reader.get_by_ids([*range(1, 1002), 9999, 1, 2, 9999])
    finally:
        event.remove(db_engine, "before_cursor_execute", capture_query)

    assert set(summaries) == set(range(1, 1002))
    assert summaries[2].is_active is False
    assert len(queries) == 3
    assert all(len(parameters) <= 500 for parameters, _ in queries)
    assert sum(len(parameters) for parameters, _ in queries) == 1002
    assert all(
        columns == ["id", "name", "address", "district_code", "is_active"] for _, columns in queries
    )


def test_readers_share_callers_transaction_without_committing(db_session_factory, venues):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    status_reader = SqlAlchemyVenueStatusReader(lambda: uow.session)
    reader = SqlAlchemyVenueReader(lambda: uow.session)
    with uow.write():
        uow.session.execute(
            update(VenueModel).where(VenueModel.id == 1).values(name="Chưa commit", is_active=False)
        )
        uow.session.add(
            VenueModel(id=3, name="Sân mới", address="Địa chỉ 3", district_code="DONG_DA")
        )
        uow.session.flush()
        assert status_reader.is_active(1) is False
        assert reader.get_by_id(1).name == "Chưa commit"
        assert set(reader.get_by_ids([1, 3])) == {1, 3}
        # Deliberately omit commit: reading must not commit the caller's writes.

    with db_session_factory() as session:
        original = session.get(VenueModel, 1)
        assert (original.name, original.is_active) == ("Sân active", True)
        assert session.get(VenueModel, 3) is None


@pytest.mark.parametrize(
    ("venue_ids", "expected"),
    [
        (
            [2, 999, 1, 2, 999],
            {
                1: VenueSummary(1, "Sân active", "Địa chỉ 1", "CAU_GIAY", True),
                2: VenueSummary(2, "Sân inactive", "Địa chỉ 2", "DONG_DA", False),
            },
        ),
        ([998, 999, 998], {}),
    ],
    ids=["mixed-with-duplicates", "all-missing"],
)
def test_batch_maps_existing_ids_without_changing_input(
    db_session_factory, venues, venue_ids, expected
):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyVenueReader(lambda: uow.session)
    original_ids = venue_ids.copy()
    with uow.read():
        summaries = reader.get_by_ids(venue_ids)
    assert summaries == expected
    assert venue_ids == original_ids


@pytest.mark.parametrize(
    ("reader_class", "method", "argument"),
    [
        (SqlAlchemyVenueStatusReader, "is_active", 1),
        (SqlAlchemyVenueReader, "get_by_id", 1),
        (SqlAlchemyVenueReader, "get_by_ids", [1]),
    ],
    ids=["status", "single-summary", "batch-summary"],
)
def test_readers_require_callers_active_uow(
    db_session_factory, venues, reader_class, method, argument
):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    read = getattr(reader_class(lambda: uow.session), method)
    with pytest.raises(RuntimeError, match="No active unit of work"):
        read(argument)
    with uow.read():
        assert read(argument) is not None
    with pytest.raises(RuntimeError, match="No active unit of work"):
        read(argument)


@pytest.mark.parametrize(
    ("reader_class", "method", "argument", "fail_on_query"),
    [
        (SqlAlchemyVenueStatusReader, "is_active", 1, 1),
        (SqlAlchemyVenueReader, "get_by_id", 1, 1),
        (SqlAlchemyVenueReader, "get_by_ids", list(range(1, 502)), 2),
    ],
    ids=["status", "single-summary", "batch-second-query"],
)
def test_query_failure_propagates_and_rolls_back_callers_changes(
    db_session_factory, db_engine, venues, reader_class, method, argument, fail_on_query
):
    queries = 0
    failure = OperationalError("SELECT venues", None, sqlite3.OperationalError("catalog failure"))

    def fail_query(connection, cursor, statement, parameters, context, executemany):
        nonlocal queries
        if statement.lstrip().upper().startswith("SELECT"):
            queries += 1
            if queries == fail_on_query:
                raise failure

    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    read = getattr(reader_class(lambda: uow.session), method)
    with pytest.raises(OperationalError) as raised:
        with uow.write():
            uow.session.execute(
                update(VenueModel).where(VenueModel.id == 1).values(name="Chưa commit")
            )
            event.listen(db_engine, "before_cursor_execute", fail_query)
            try:
                read(argument)
            finally:
                event.remove(db_engine, "before_cursor_execute", fail_query)

    assert raised.value is failure
    assert queries == fail_on_query
    with db_session_factory() as session:
        assert session.get(VenueModel, 1).name == "Sân active"
