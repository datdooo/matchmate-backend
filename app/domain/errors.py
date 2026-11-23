from typing import Any


class DomainError(Exception):
    def __init__(self, code: str, message: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class DatabaseBusyError(Exception):
    """Không lấy được khóa ghi DB trong thời gian cho phép."""


class DatabaseTimeoutError(Exception):
    """Câu lệnh vượt quá thời gian thực thi cho phép."""


class DatabaseUnavailableError(Exception):
    def __init__(self, *, outcome_unknown: bool = False) -> None:
        super().__init__()
        self.outcome_unknown = outcome_unknown
