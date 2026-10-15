"""Thin SQLAlchemy Unit of Work with SQLite BEGIN IMMEDIATE semantics."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

_SQLITE_PRIMARY_MASK = 0xFF


class DatabaseBusy(RuntimeError):
    """SQLite could not obtain the write lock within busy_timeout."""

    code = "DATABASE_BUSY"


class InternalDatabaseError(RuntimeError):
    """Unclassified database failure that must not be exposed verbatim."""

    code = "INTERNAL_ERROR"


def sqlite_primary_error_code(error: BaseException) -> int | None:
    """Read the SQLite primary code from Python 3.11+ driver exceptions."""
    raw = getattr(error, "sqlite_errorcode", None)
    if not isinstance(raw, int):
        return None
    return raw & _SQLITE_PRIMARY_MASK


def is_sqlite_busy(error: BaseException) -> bool:
    """Match SQLITE_BUSY and every extended result code in the BUSY family."""
    return sqlite_primary_error_code(error) == sqlite3.SQLITE_BUSY


def _raise_mapped_database_error(exc: DBAPIError) -> None:
    origin = exc.orig
    if isinstance(origin, BaseException) and is_sqlite_busy(origin):
        raise DatabaseBusy("SQLite writer lock timed out") from exc
    raise InternalDatabaseError("database operation failed") from exc


@dataclass
class DatabaseTransaction:
    """One SQLAlchemy Session/transaction owned by a UoW context."""

    session: Session
    committed: bool = False

    def commit(self) -> None:
        self.session.commit()
        self.committed = True


class SqlAlchemyUnitOfWork:
    """Own read/write transaction lifecycle without leaking it into services."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def write(self) -> Iterator[DatabaseTransaction]:
        session = self._session_factory()
        transaction = DatabaseTransaction(session=session)
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield transaction
            if not transaction.committed:
                session.rollback()
        except DBAPIError as exc:
            session.rollback()
            _raise_mapped_database_error(exc)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def read(self) -> Iterator[DatabaseTransaction]:
        session = self._session_factory()
        transaction = DatabaseTransaction(session=session)
        try:
            yield transaction
        except DBAPIError as exc:
            session.rollback()
            _raise_mapped_database_error(exc)
        finally:
            session.rollback()
            session.close()
