import os
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Base, MatchingRequestModel, ParticipationModel, VenueModel
from app.db.session import create_db_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DatabaseBusyError, DatabaseTimeoutError
from scripts.import_sqlite_to_postgres import import_sqlite
from scripts.prepare_member2_phase1 import prepare


@pytest.fixture
def postgres(monkeypatch):
    url = os.getenv("MATCHMATE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set MATCHMATE_TEST_POSTGRES_URL to a disposable PostgreSQL server")
    admin = create_db_engine(url)
    database = f"matchmate_test_{uuid4().hex}"
    engine = None
    created = False
    try:
        if admin.dialect.name != "postgresql":
            pytest.fail("MATCHMATE_TEST_POSTGRES_URL must point to PostgreSQL")
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {database}")
            created = True
        target_url = admin.url.set(database=database).render_as_string(hide_password=False)
        monkeypatch.setenv("DATABASE_URL", target_url)
        command.upgrade(Config("alembic.ini"), "head")
        engine = create_db_engine(target_url)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    connection.exec_driver_sql(f"DROP DATABASE {database}")
        finally:
            admin.dispose()


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "fixture"
    prepare(path)
    return path / "migration-source.db"


@pytest.fixture
def db_session_factory(postgres):
    return create_session_factory(postgres)


def test_migration_import_sequences_and_constraints(postgres, source):
    assert import_sqlite(source, postgres) == {
        "venues": 1,
        "users": 3,
        "sessions": 1,
        "participations": 4,
        "matching_requests": 3,
    }
    command.check(Config("alembic.ini"))
    with pytest.raises(ValueError, match="existing rows"):
        import_sqlite(source, postgres)

    with postgres.connect() as connection:
        for table in Base.metadata.sorted_tables:
            highest_id = connection.scalar(select(func.max(table.c.id)))
            seq = connection.exec_driver_sql(
                "SELECT pg_get_serial_sequence(%s, 'id')", (table.name,)
            ).scalar_one()
            assert (
                connection.exec_driver_sql("SELECT nextval(%s)", (seq,)).scalar_one() > highest_id
            )

    for model, active_status, index in (
        (ParticipationModel, "ACCEPTED", "uq_participations_active"),
        (MatchingRequestModel, "ACTIVE", "uq_matching_requests_active_user"),
    ):
        table = model.__table__
        with pytest.raises(IntegrityError) as duplicate, postgres.begin() as connection:
            active = (
                connection.execute(select(table).where(table.c.status == active_status).limit(1))
                .mappings()
                .one()
            )
            connection.execute(
                table.insert(), {key: val for key, val in active.items() if key != "id"}
            )
        assert duplicate.value.orig.diag.constraint_name == index


def test_import_rolls_back_all_tables_on_failure(postgres, source):
    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE matching_requests SET id = ? WHERE id = (SELECT max(id) FROM "
            "matching_requests)",
            (2**63 - 1,),
        )
    with pytest.raises(ValueError, match="No automatic IDs"):
        import_sqlite(source, postgres)
    with postgres.connect() as connection:
        for table in Base.metadata.sorted_tables:
            assert connection.scalar(select(func.count()).select_from(table)) == 0


@pytest.mark.parametrize("lock_method", ["lock_session", "lock_user"])
def test_row_lock_uses_independent_connections_and_rolls_back(
    postgres, source, db_session_factory, lock_method
):
    import_sqlite(source, postgres)
    model = Base.metadata.tables["sessions" if lock_method == "lock_session" else "users"]
    first = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    second = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    with first.write():
        row_id = first.session.scalar(select(func.min(model.c.id)))
        first_pid = first.session.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar()
        assert getattr(first, lock_method)(row_id) is True
        assert getattr(first, lock_method)(2**63 - 1) is False
        with pytest.raises(DatabaseBusyError), second.write():
            connection = second.session.connection()
            assert connection.exec_driver_sql("SELECT pg_backend_pid()").scalar() != first_pid
            connection.exec_driver_sql("SET LOCAL lock_timeout = '150ms'")
            second.session.add(VenueModel(name="Rollback", address="Test", district_code="TEST"))
            second.session.flush()
            getattr(second, lock_method)(row_id)

    with second.write():
        assert getattr(second, lock_method)(row_id) is True
        assert second.session.scalar(select(func.count()).select_from(VenueModel)) == 1


def test_postgres_snapshot_and_statement_timeout(db_session_factory):
    reader = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    writer = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    count = select(func.count()).select_from(VenueModel)
    with reader.read():
        assert reader.session.scalar(count) == 0
        assert (
            reader.session.connection().exec_driver_sql("SHOW transaction_read_only").scalar()
            == "on"
        )
        with writer.write():
            writer.session.add(VenueModel(name="New", address="Test", district_code="TEST"))
            writer.commit()
        assert reader.session.scalar(count) == 0
    with reader.read():
        assert reader.session.scalar(count) == 1
    with pytest.raises(DatabaseTimeoutError), writer.write():
        connection = writer.session.connection()
        connection.exec_driver_sql("SET LOCAL statement_timeout = '100ms'")
        connection.exec_driver_sql("SELECT pg_sleep(1)")


def test_api_lifecycle_and_matching_on_migrated_postgres(postgres, source, client):
    import_sqlite(source, postgres)
    response = client.get("/venues")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    with postgres.connect() as connection:
        venue_id = connection.scalar(select(VenueModel.id))

    def register_and_login(name, gender):
        credentials = {"email": f"{name}@example.com", "password": "test-only-password"}
        payload = credentials | {"display_name": name, "skill_level": "TB", "gender": gender}
        assert client.post("/auth/register", json=payload).status_code == 201
        login = client.post("/auth/login", json=credentials)
        assert login.status_code == 200, login.text
        return {"Authorization": "Bearer " + login.json()["access_token"]}

    host = register_and_login("postgres-host", "MALE")
    player = register_and_login("postgres-player", "FEMALE")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    slot = {
        "venue_id": venue_id,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "play_type": "SINGLES",
    }
    game = client.post(
        "/sessions",
        headers=host,
        json=slot
        | {
            "title": "Kèo kiểm thử PostgreSQL",
            "fee_male_vnd": 60000,
            "fee_female_vnd": 40000,
            "min_level": "TB_MINUS",
            "max_level": "TB_PLUS",
        },
    )
    assert game.status_code == 201, game.text
    game_id = game.json()["id"]
    matching = client.post(
        "/matching/requests",
        headers=player,
        json=slot
        | {
            "proposed_fee_male_vnd": 60000,
            "proposed_fee_female_vnd": 40000,
            "budget_max_vnd": 60000,
        },
    )
    assert matching.status_code == 201, matching.text
    matching_id = matching.json()["request"]["id"]
    pending = client.post("/participations", headers=player, json={"session_id": game_id})
    assert pending.status_code == 201, pending.text
    approved = client.post(
        f"/participations/{pending.json()['id']}/decision",
        headers=host,
        json={"decision": "APPROVE"},
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/sessions/{game_id}", headers=player)
    assert detail.status_code == 200, detail.text
    assert detail.json()["accepted_count"] == 2
    with postgres.connect() as connection:
        closed = connection.execute(
            select(MatchingRequestModel.status, MatchingRequestModel.closed_reason).where(
                MatchingRequestModel.id == matching_id
            )
        ).one()
    assert closed == ("CLOSED", "CONFIRMED")
