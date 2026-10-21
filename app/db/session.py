import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

def create_db_engine(
    database_url: str,
    busy_timeout: int = 5000,
) -> Engine:
    """Tạo engine SQLite và cấu hình các connection."""
    # Kiểm đúng kiểu int để loại cả True/False.
    if type(busy_timeout) is not int or busy_timeout < 0:
        raise ValueError("busy_timeout must be a non-negative integer")

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    # PRAGMA áp dụng riêng cho từng connection, nên cấu hình ngay khi mở mới.
    @event.listens_for(engine, "connect")
    def configure_connection(
        connection: sqlite3.Connection,
        _record: object,
    ) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            # Thời gian chờ khóa ghi tính bằng mili giây, mặc định 5 giây.
            cursor.execute(f"PRAGMA busy_timeout = {busy_timeout}")
        finally:
            cursor.close()

    return engine

engine = create_db_engine(DATABASE_URL)

def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Tạo bộ cấp DB Session để repository sử dụng."""
    return sessionmaker(
        bind=engine,
        # Repository chủ động flush khi cần ghi dữ liệu.
        autoflush=False,
        # Giữ dữ liệu ORM đã nạp sau khi commit.
        expire_on_commit=False,
    )
