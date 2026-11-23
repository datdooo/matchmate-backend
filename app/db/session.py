import os
import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


def create_db_engine(
    database_url: str,
    busy_timeout: int = 5000,
) -> Engine:
    """Tạo engine và đặt cấu hình kết nối cho từng hệ quản trị."""
    url = make_url(database_url)
    if url.get_backend_name() == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
        lock_ms = int(os.getenv("POSTGRES_LOCK_TIMEOUT_MS", "5000"))
        statement_ms = int(os.getenv("POSTGRES_STATEMENT_TIMEOUT_MS", "15000"))
        if not 0 < lock_ms < statement_ms:
            raise ValueError("PostgreSQL timeouts must satisfy 0 < lock < statement")
        return create_engine(
            url,
            pool_size=5,
            max_overflow=0,
            pool_timeout=5,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 5,
                "options": (
                    f"-c timezone=UTC -c lock_timeout={lock_ms} -c statement_timeout={statement_ms}"
                ),
            },
        )
    if url.get_backend_name() != "sqlite":
        raise ValueError("DATABASE_URL must point to SQLite or PostgreSQL")

    # Kiểm đúng kiểu int để loại cả True/False.
    if type(busy_timeout) is not int or busy_timeout < 0:
        raise ValueError("busy_timeout must be a non-negative integer")

    engine = create_engine(
        url,
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


engine = create_db_engine(
    DATABASE_URL, busy_timeout=int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"))
)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Tạo bộ cấp DB Session để repository sử dụng."""
    return sessionmaker(
        bind=engine,
        # Repository chủ động flush khi cần ghi dữ liệu.
        autoflush=False,
        # Giữ dữ liệu ORM đã nạp sau khi commit.
        expire_on_commit=False,
    )
