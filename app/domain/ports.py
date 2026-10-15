"""Small shared ports owned by the transaction boundary."""

from __future__ import annotations

from datetime import datetime
from typing import ContextManager, Protocol


class Clock(Protocol):
    """Provide the current UTC-aware instant."""

    def now(self) -> datetime: ...


class UnitOfWorkTransaction(Protocol):
    """Minimum transaction surface exposed to services."""

    def commit(self) -> None: ...


class UnitOfWork(Protocol):
    """Shared read/write transaction boundary."""

    def write(self) -> ContextManager[UnitOfWorkTransaction]: ...

    def read(self) -> ContextManager[UnitOfWorkTransaction]: ...


class MatchingRequestWriter(Protocol):
    """Close matching requests after a schedule becomes confirmed."""

    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None: ...
