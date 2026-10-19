from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Self

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.db.errors import is_database_busy


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

            try:
                # BEGIN tường minh để cả thao tác đọc cũng có snapshot.
                statement = "BEGIN IMMEDIATE" if write else "BEGIN"
                session.connection().exec_driver_sql(statement)

                # Service chỉ đọc Clock sau khi BEGIN thành công.
                yield self
            except DBAPIError as error:
                if is_database_busy(error):
                    raise self._busy_error_factory() from error
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

    def commit(self) -> None:
        """Commit một lần khi thao tác ghi đã hoàn thành."""
        session = self.session

        if not self._write_mode:
            raise RuntimeError("Cannot commit a read unit of work")

        session.commit()
        self._committed = True
