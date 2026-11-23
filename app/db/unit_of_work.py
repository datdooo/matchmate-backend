import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Self

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError
from sqlalchemy.orm import Session, sessionmaker

from app.db.errors import is_connection_failure, is_database_busy, is_statement_timeout, sqlstate
from app.db.models import SessionModel, UserModel
from app.domain.errors import DatabaseTimeoutError, DatabaseUnavailableError

logger = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork:
    """Quản lý DB Session và transaction cho một thao tác nghiệp vụ."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        busy_error_factory: Callable[[], Exception],
    ) -> None:
        self._session_factory = session_factory
        self._busy_error_factory = busy_error_factory
        self._session: Session | None = None
        self._write_mode = False
        self._committed = False

    @property
    def session(self) -> Session:
        """DB Session cho các repository, chỉ dùng trong transaction."""
        if self._session is None:
            raise RuntimeError("No active unit of work")
        if self._committed:
            raise RuntimeError("Unit of work already committed")

        return self._session

    def write(self) -> AbstractContextManager[Self]:
        return self._transaction(write=True)

    def read(self) -> AbstractContextManager[Self]:
        return self._transaction(write=False)

    @contextmanager
    def _transaction(self, write: bool) -> Iterator[Self]:
        if self._session is not None:
            raise RuntimeError("Nested unit of work is not allowed")

        with self._session_factory() as session:
            self._session = session
            self._write_mode = write
            self._committed = False
            postgres = session.get_bind().dialect.name == "postgresql"

            try:
                if postgres:
                    self._begin_postgres(session, write)
                else:
                    statement = "BEGIN IMMEDIATE" if write else "BEGIN"
                    session.connection().exec_driver_sql(statement)
                yield self
            except TimeoutError as error:
                if postgres:
                    raise self._busy_error_factory() from error
                raise
            except DBAPIError as error:
                if is_database_busy(error):
                    raise self._busy_error_factory() from error
                if postgres:
                    if is_statement_timeout(error):
                        raise DatabaseTimeoutError() from error
                    if is_connection_failure(error):
                        raise DatabaseUnavailableError() from error
                    if sqlstate(error) == "57014":
                        logger.warning("query_cancelled_unknown")
                raise
            finally:
                try:
                    # Nếu đã commit thì rollback này không làm thay đổi dữ liệu.
                    # Nếu chưa commit hoặc có lỗi thì hủy toàn bộ phần đang làm.
                    session.rollback()
                finally:
                    self._session = None
                    self._write_mode = False
                    self._committed = False

    @staticmethod
    def _begin_postgres(session: Session, write: bool) -> None:
        try:
            connection = session.connection()
        except OperationalError as error:
            # libpq may fail to connect before it receives a SQLSTATE.
            if sqlstate(error) is None:
                raise DatabaseUnavailableError() from error
            raise
        isolation = "READ COMMITTED, READ WRITE" if write else "REPEATABLE READ, READ ONLY"
        connection.exec_driver_sql(f"SET TRANSACTION ISOLATION LEVEL {isolation}")

    def lock_session(self, session_id: int) -> bool:
        return self._lock_row(SessionModel, session_id)

    def lock_user(self, user_id: int) -> bool:
        return self._lock_row(UserModel, user_id)

    def _lock_row(self, model: type[SessionModel] | type[UserModel], row_id: int) -> bool:
        session = self.session
        if not self._write_mode:
            raise RuntimeError("Row locks require a write unit of work")
        statement = select(model.id).where(model.id == row_id)
        if session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        # SQLite's BEGIN IMMEDIATE already protects the whole write operation.
        return session.scalar(statement) is not None

    def commit(self) -> None:
        """Commit một lần khi thao tác ghi đã hoàn thành."""
        session = self.session

        if not self._write_mode:
            raise RuntimeError("Cannot commit a read unit of work")

        try:
            session.commit()
        except DBAPIError as error:
            if session.get_bind().dialect.name == "postgresql" and is_connection_failure(error):
                raise DatabaseUnavailableError(outcome_unknown=True) from error
            raise
        self._committed = True
