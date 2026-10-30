import sqlite3

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import VenueModel
from app.db.session import create_db_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork


class FakeDatabaseBusy(Exception):
    """Lỗi giả để kiểm UoW báo hết thời gian chờ khóa."""


@pytest.fixture
def uow(
    db_session_factory: sessionmaker[Session],
) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(
        db_session_factory,
        busy_error_factory=FakeDatabaseBusy,
    )


def make_venue(name: str) -> VenueModel:
    return VenueModel(
        name=name,
        address="Địa điểm giả lập",
        district_code="CAU_GIAY",
    )


def count_venues(factory: sessionmaker[Session]) -> int:
    """Đọc bằng Session mới để kiểm dữ liệu thực sự trong DB."""
    with factory() as session:
        return session.scalar(select(func.count()).select_from(VenueModel))


def test_commit_persists_data(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    with uow.write():
        uow.session.add(make_venue("Sân đã commit"))
        uow.commit()

    assert count_venues(db_session_factory) == 1


def test_missing_commit_rolls_back(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    with uow.write():
        uow.session.add(make_venue("Sân chưa commit"))
        # Đẩy INSERT xuống DB để chắc chắn rollback được kiểm thật.
        uow.session.flush()

    assert count_venues(db_session_factory) == 0


def test_exception_rolls_back_all_changes(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(ValueError, match="business operation failed"):
        with uow.write():
            uow.session.add(make_venue("Sân A"))
            uow.session.flush()

            uow.session.add(make_venue("Sân B"))
            uow.session.flush()

            raise ValueError("business operation failed")

    assert count_venues(db_session_factory) == 0


def test_read_cannot_commit(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(RuntimeError, match="Cannot commit a read"):
        with uow.read():
            uow.session.add(make_venue("Sân trong thao tác đọc"))
            uow.session.flush()
            uow.commit()

    assert count_venues(db_session_factory) == 0


def test_busy_timeout_blocks_body_and_allows_reuse(
    db_engine: Engine,
    db_session_factory: sessionmaker[Session],
) -> None:
    """Không lấy được khóa thì chưa chạy nghiệp vụ; UoW vẫn dùng lại được."""
    # Cùng DB với fixture, nhưng timeout ngắn để test chạy nhanh.
    contender_engine = create_db_engine(
        db_engine.url.render_as_string(hide_password=False),
        busy_timeout=20,
    )
    contender_factory = create_session_factory(contender_engine)
    contender = SqlAlchemyUnitOfWork(
        contender_factory,
        busy_error_factory=FakeDatabaseBusy,
    )
    entered_body = False

    try:
        with db_engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")

            with pytest.raises(FakeDatabaseBusy):
                with contender.write():
                    entered_body = True

            assert entered_body is False
            assert count_venues(db_session_factory) == 0
            blocker.rollback()

        # Khóa đã được nhả; thử lại bằng một thao tác mới, có chủ đích.
        with contender.write():
            contender.session.add(make_venue("Sân sau khi nhả khóa"))
            contender.commit()

        assert count_venues(db_session_factory) == 1
    finally:
        contender_engine.dispose()


def test_check_error_rolls_back_without_becoming_busy(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    """Lỗi CHECK giữ đúng loại lỗi và hủy cả dữ liệu đã ghi trước đó."""
    with pytest.raises(IntegrityError) as caught:
        with uow.write():
            uow.session.add(make_venue("Sân sẽ bị rollback"))
            uow.session.flush()

            # Gửi SQL trực tiếp để kiểm CHECK của SQLite, bỏ qua kiểm kiểu ORM.
            uow.session.connection().exec_driver_sql("UPDATE venues SET is_active = 2")
            uow.commit()

    assert caught.value.orig.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_CHECK
    assert count_venues(db_session_factory) == 0


def test_read_opens_transaction_on_same_connection(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    """Chế độ đọc phải mở transaction thật trên connection đang dùng."""
    with uow.read():
        first = uow.session.connection()
        second = uow.session.connection()

        assert first is second

        # SQLite mặc định có thể chưa BEGIN khi chỉ SELECT.
        # Kiểm driver để xác nhận UoW đã mở transaction tường minh.
        driver = first.connection.driver_connection
        assert driver is not None
        assert driver.in_transaction is True

        assert uow.session.scalar(select(func.count()).select_from(VenueModel)) == 0


def test_cannot_commit_twice(
    uow: SqlAlchemyUnitOfWork,
    db_session_factory: sessionmaker[Session],
) -> None:
    """Commit lần hai bị chặn; lần commit đầu vẫn giữ dữ liệu."""
    with uow.write():
        uow.session.add(make_venue("Sân commit một lần"))
        uow.commit()

        with pytest.raises(RuntimeError, match="already committed"):
            uow.commit()

    assert count_venues(db_session_factory) == 1
