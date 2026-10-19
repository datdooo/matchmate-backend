from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol, Self


class Clock(Protocol):
    """Cung cấp thời gian để Service có thể dùng đồng hồ giả khi test."""

    def now(self) -> datetime:
        """Trả thời gian hiện tại dưới dạng UTC có múi giờ."""
        ...


class UnitOfWork(Protocol):
    """Quản lý một thao tác dùng chung connection và transaction."""

    def write(self) -> AbstractContextManager[Self]:
        """Lấy khóa ghi bằng BEGIN IMMEDIATE trước khi vào khối with.

        Service đọc Clock sau khi vào khối này.
        Nếu có lỗi hoặc chưa commit thì rollback khi thoát.
        """
        ...

    def read(self) -> AbstractContextManager[Self]:
        """Giữ cùng snapshot cho các truy vấn trong một thao tác đọc."""
        ...

    def commit(self) -> None:
        """Commit thao tác ghi; chỉ gọi một lần khi thành công."""
        ...


class MatchingRequestWriter(Protocol):
    """Đóng nhu cầu matching khi người chơi có lịch được xác nhận."""

    def close_overlapping(
        self,
        user_id: int,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> None:
        """Đóng các nhu cầu ACTIVE chồng lịch với lý do CONFIRMED.

        Dùng transaction hiện tại và không tự commit.
        """
        ...
