"""Các actor dùng connection riêng tới cùng SQLite file; kiểm lại invariant sau commit."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

import pytest
from sqlalchemy import event, func, select

from app.db.models import ParticipationModel, SessionModel
from app.db.session import create_db_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.errors import DomainError
from app.features.auth.contracts import DatabaseBusyError
from app.features.auth.repository import SqlAlchemyUserRepository
from app.features.sessions.session_repository import SqlAlchemySessionRepository
from app.features.sessions.session_service import SessionService


def outcome(operation):
    try:
        operation()
        return "OK"
    except DomainError as error:
        return error.code


def run_pair(first, second):
    gate = Barrier(2)

    def run(operation):
        gate.wait(timeout=3)
        return outcome(operation)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, operation) for operation in (first, second)]
        return [future.result(timeout=10) for future in futures]


def test_two_approvals_compete_for_last_place(service, make_service, game_data, db_session_factory):
    first = service.join(game_data["player"], game_data["first"])
    second = service.join(game_data["other"], game_data["first"])
    with db_session_factory() as session:
        session.get(SessionModel, game_data["first"]).play_type = "SINGLES"
        session.commit()
    results = run_pair(
        lambda: make_service().decide(game_data["host"], first.id, "APPROVE"),
        lambda: make_service().decide(game_data["host"], second.id, "APPROVE"),
    )
    assert sorted(results) == ["OK", "SESSION_FULL"]
    with db_session_factory() as session:
        accepted = session.scalar(
            select(func.count())
            .select_from(ParticipationModel)
            .where(
                ParticipationModel.session_id == game_data["first"],
                ParticipationModel.status == "ACCEPTED",
            )
        )
        assert accepted == 2  # host và đúng một người thắng quyền ghi


def test_same_player_cannot_be_approved_into_overlapping_games(
    service,
    make_service,
    game_data,
    db_session_factory,
):
    with db_session_factory() as session:
        first_game = session.get(SessionModel, game_data["first"])
        second_game = session.get(SessionModel, game_data["second"])
        second_game.starts_at = first_game.starts_at + timedelta(minutes=30)
        second_game.host_user_id = game_data["other"]
        host_part = session.scalar(
            select(ParticipationModel).where(
                ParticipationModel.session_id == game_data["second"],
                ParticipationModel.user_id == game_data["host"],
            )
        )
        host_part.user_id = game_data["other"]
        session.commit()
    first = service.join(game_data["player"], game_data["first"])
    second = service.join(game_data["player"], game_data["second"])
    results = run_pair(
        lambda: make_service().decide(game_data["host"], first.id, "APPROVE"),
        lambda: make_service().decide(game_data["other"], second.id, "APPROVE"),
    )
    assert sorted(results) == ["OK", "TIME_CONFLICT"]
    with db_session_factory() as session:
        statuses = session.scalars(
            select(ParticipationModel.status).where(
                ParticipationModel.user_id == game_data["player"]
            )
        ).all()
        assert sorted(statuses) == ["ACCEPTED", "PENDING"]


def test_approval_against_withdrawal(service, make_service, game_data, db_session_factory):
    pending = service.join(game_data["player"], game_data["first"])
    approved, withdrawn = run_pair(
        lambda: make_service().decide(game_data["host"], pending.id, "APPROVE"),
        lambda: make_service().withdraw(game_data["player"], pending.id),
    )
    assert approved in {"OK", "INVALID_STATE"} and withdrawn == "OK"
    with db_session_factory() as session:
        assert session.get(ParticipationModel, pending.id).status == "CANCELLED"
        accepted = session.scalars(
            select(ParticipationModel.id).where(
                ParticipationModel.session_id == game_data["first"],
                ParticipationModel.status == "ACCEPTED",
            )
        ).all()
        assert len(accepted) == 1


def test_approval_against_session_cancellation(
    service,
    make_service,
    game_data,
    db_session_factory,
    clock,
):
    pending = service.join(game_data["player"], game_data["first"])

    def cancel():
        # Dùng luồng hủy thật, với connection riêng đối đầu thao tác duyệt.
        uow = SqlAlchemyUnitOfWork(db_session_factory, DatabaseBusyError)
        with uow.write():
            SessionService(
                SqlAlchemySessionRepository(uow.session),
                SqlAlchemyUserRepository(uow.session),
                clock,
            ).cancel(game_data["first"], game_data["host"])
            uow.commit()

    approved, cancelled = run_pair(
        lambda: make_service().decide(game_data["host"], pending.id, "APPROVE"),
        cancel,
    )
    assert approved in {"OK", "INVALID_STATE", "SESSION_CANCELLED"} and cancelled == "OK"
    with db_session_factory() as session:
        assert session.get(SessionModel, game_data["first"]).status == "CANCELLED"
        statuses = session.scalars(
            select(ParticipationModel.status).where(
                ParticipationModel.session_id == game_data["first"]
            )
        ).all()
        assert statuses and set(statuses) == {"CANCELLED"}


def test_clock_is_read_after_waiting_for_writer_lock(
    make_service,
    game_data,
    db_session_factory,
    db_engine,
    clock,
    monkeypatch,
):
    contender = create_db_engine(str(db_engine.url), busy_timeout=1000)
    factory = create_session_factory(contender)
    began = Event()
    reads = []
    with db_session_factory() as session:
        starts_at = session.get(SessionModel, game_data["first"]).starts_at

    @event.listens_for(contender, "before_cursor_execute")
    def before_execute(_conn, _cursor, statement, _params, _context, _many):
        if statement == "BEGIN IMMEDIATE":
            began.set()

    def now():
        assert began.is_set(), "Clock bị đọc trước khi bắt đầu lấy quyền ghi"
        reads.append(clock.value)
        return clock.value

    monkeypatch.setattr(clock, "now", now)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with db_engine.connect() as blocker:
                blocker.exec_driver_sql("BEGIN IMMEDIATE")
                future = pool.submit(
                    outcome,
                    lambda: make_service(factory=factory).join(
                        game_data["player"], game_data["first"]
                    ),
                )
                assert began.wait(timeout=3)
                # Dùng đồng hồ giả để qua biên starts_at, không sleep hay phụ thuộc tốc độ máy.
                clock.value = starts_at
                blocker.rollback()
                assert future.result(timeout=5) == "SESSION_ALREADY_STARTED"
        assert reads == [starts_at]
        with db_session_factory() as session:
            assert (
                session.scalar(
                    select(ParticipationModel.id).where(
                        ParticipationModel.user_id == game_data["player"]
                    )
                )
                is None
            )
    finally:
        contender.dispose()


def test_lock_timeout_never_enters_business_operation(
    make_service,
    game_data,
    db_engine,
    db_session_factory,
    clock,
    monkeypatch,
):
    contender = create_db_engine(str(db_engine.url), busy_timeout=20)
    factory = create_session_factory(contender)

    def unexpected_clock():
        raise AssertionError("Chưa lấy được quyền ghi thì chưa được đọc Clock")

    monkeypatch.setattr(clock, "now", unexpected_clock)
    try:
        with db_engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            with pytest.raises(DatabaseBusyError):
                make_service(factory=factory).join(game_data["player"], game_data["first"])
            blocker.rollback()
        with db_session_factory() as session:
            assert (
                session.scalar(
                    select(ParticipationModel.id).where(
                        ParticipationModel.user_id == game_data["player"]
                    )
                )
                is None
            )
    finally:
        contender.dispose()
