import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError, OperationalError

from app.db.errors import is_database_busy
from app.db.session import create_db_engine


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (sqlite3.SQLITE_BUSY, True),
        (sqlite3.SQLITE_BUSY_RECOVERY, True),
        (sqlite3.SQLITE_BUSY_SNAPSHOT, True),
        (sqlite3.SQLITE_LOCKED, False),
        (sqlite3.SQLITE_CONSTRAINT_CHECK, False),
        (sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY, False),
        (sqlite3.SQLITE_CONSTRAINT_NOTNULL, False),
    ],
)
def test_classifies_sqlite_error_code(code: int, expected: bool) -> None:
    """Kiểm mã thường, mã mở rộng và các nhóm không phải BUSY."""
    original = sqlite3.OperationalError("test error")
    original.sqlite_errorcode = code
    error = DBAPIError(None, None, original)

    assert is_database_busy(error) is expected


def test_does_not_guess_busy_from_message() -> None:
    """Thông báo giống lỗi khóa chưa đủ để kết luận là BUSY."""
    original = sqlite3.OperationalError("database is locked")
    error = DBAPIError(None, None, original)

    assert is_database_busy(error) is False


def test_recognizes_real_write_lock_timeout(tmp_path: Path) -> None:
    """Connection thứ hai hết thời gian chờ khi writer đầu giữ khóa."""
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'busy.db'}",
        busy_timeout=20,
    )

    try:
        with engine.connect() as first, engine.connect() as second:
            first.exec_driver_sql("BEGIN IMMEDIATE")

            with pytest.raises(OperationalError) as caught:
                second.exec_driver_sql("BEGIN IMMEDIATE")

            assert is_database_busy(caught.value) is True

            second.rollback()
            first.rollback()
    finally:
        engine.dispose()
