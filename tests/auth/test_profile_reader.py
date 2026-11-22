from datetime import datetime, timezone

from sqlalchemy import event, update

from app.db.models import UserModel
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.enums import Gender, skill_to_rank
from app.domain.errors import DatabaseBusyError
from app.features.auth.infrastructure.player_profile_reader import SqlAlchemyPlayerProfileReader


def test_batch_profiles_only_select_public_fields_and_split_queries(db_session_factory, db_engine):
    now = datetime(2030, 11, 1, tzinfo=timezone.utc)
    with db_session_factory.begin() as db:
        db.add_all(
            UserModel(
                id=i,
                email=f"{i}@example.invalid",
                password_hash="fixture-only",
                display_name=f"Player {i}",
                skill_level=19 if i == 2 else 1,
                gender="UNSPECIFIED" if i == 2 else "MALE",
                created_at=now,
                updated_at=now,
            )
            for i in range(1, 1002)
        )
    queries = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append((parameters, list(context.compiled.statement.selected_columns.keys())))

    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyPlayerProfileReader(lambda: uow.session)
    event.listen(db_engine, "before_cursor_execute", capture)
    try:
        with uow.read():
            profiles = reader.get_by_ids([*range(1, 1002), 9999, 1, 2])
    finally:
        event.remove(db_engine, "before_cursor_execute", capture)
    assert set(profiles) == set(range(1, 1002))
    assert len(queries) == 3
    assert sum(len(parameters) for parameters, _ in queries) == 1002
    assert all(len(parameters) <= 500 for parameters, _ in queries)
    assert all(columns == ["id", "display_name", "skill_level", "gender"] for _, columns in queries)
    assert skill_to_rank(profiles[1].skill_level) == 1
    assert skill_to_rank(profiles[2].skill_level) == 19
    assert profiles[2].gender == Gender.UNSPECIFIED
    assert not hasattr(profiles[1], "email") and not hasattr(profiles[1], "password_hash")


def test_empty_profile_batch_never_accesses_session():
    def forbidden():
        raise AssertionError("Empty batch accessed DB")

    assert SqlAlchemyPlayerProfileReader(forbidden).get_by_ids([]) == {}


def test_profile_reader_uses_caller_transaction_and_keeps_missing_none(
    db_session_factory, game_data
):
    uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
    reader = SqlAlchemyPlayerProfileReader(lambda: uow.session)
    with uow.write():
        db = uow.session
        cached = db.get(UserModel, game_data["player"])
        original = cached.display_name
        db.execute(
            update(UserModel.__table__)
            .where(UserModel.id == cached.id)
            .values(display_name="Changed", skill_level=19, gender="UNSPECIFIED")
        )
        profile = reader.get_by_id(cached.id)
        assert profile.display_name == "Changed"
        assert skill_to_rank(profile.skill_level) == 19
        assert profile.gender == Gender.UNSPECIFIED
        assert reader.get_by_id(9999) is None
        assert reader.get_by_ids([9999]) == {}
    with db_session_factory() as db:
        assert db.get(UserModel, game_data["player"]).display_name == original
