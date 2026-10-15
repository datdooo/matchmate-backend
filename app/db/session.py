"""SQLite engine/session configuration."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_engine(database_url: str, *, busy_timeout_ms: int = 5000) -> Engine:
    """Create the Phase 1 SQLite engine with mandatory connection PRAGMAs."""
    if not database_url.startswith("sqlite:"):
        raise ValueError("Phase 1 requires a SQLite DATABASE_URL")
    if busy_timeout_ms < 0:
        raise ValueError("busy_timeout_ms must be non-negative")

    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": busy_timeout_ms / 1000,
        },
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return independent SQLAlchemy sessions with no implicit post-commit refresh."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, autoflush=False)
