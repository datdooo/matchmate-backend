"""Hợp đồng đọc dữ liệu sân do Catalog sở hữu."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VenueSummary:
    id: int
    name: str
    address: str
    district_code: str
    is_active: bool


class VenueStatusReader(Protocol):
    """Đọc trạng thái sân trong transaction bên gọi, không tự commit."""

    def is_active(self, venue_id: int) -> bool | None:
        """Trả None nếu sân không tồn tại, False nếu inactive, True nếu active.

        Use case ánh xạ None thành VENUE_NOT_FOUND, False thành VENUE_INACTIVE.
        True chỉ xác nhận trạng thái sân, chưa xác nhận toàn bộ yêu cầu hợp lệ.
        """
        ...


class VenueReader(Protocol):
    """Đọc projection năm trường, gồm cả sân inactive phục vụ lịch sử.

    Adapter trả DTO trong transaction bên gọi, không tự mở UoW hoặc commit.
    """

    def get_by_id(self, venue_id: int) -> VenueSummary | None:
        """Trả DTO của sân, hoặc None khi ID không tồn tại."""
        ...

    def get_by_ids(self, venue_ids: list[int]) -> dict[int, VenueSummary]:
        """Loại ID trùng và bỏ ID không tồn tại khỏi kết quả.

        Đầu vào rỗng trả {} không query. Adapter chia batch tối đa 500 ID mỗi
        câu query, không giới hạn tổng số ID đầu vào. Không cam kết thứ tự dict.
        """
        ...
