from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import VenueModel
from app.features.catalog.contracts import VenueSummary

_BATCH_SIZE = 500
_SUMMARY_COLUMNS = (
    VenueModel.id,
    VenueModel.name,
    VenueModel.address,
    VenueModel.district_code,
    VenueModel.is_active,
)


class SqlAlchemyVenueStatusReader:
    """Đọc trạng thái sân bằng session của UoW bên gọi."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def is_active(self, venue_id: int) -> bool | None:
        session = self._session_provider()
        query = select(VenueModel.is_active).where(VenueModel.id == venue_id)
        return session.scalar(query)


class SqlAlchemyVenueReader:
    """Đọc DTO sân, gồm cả inactive, không mở transaction hoặc commit riêng."""

    def __init__(self, session_provider: Callable[[], Session]) -> None:
        self._session_provider = session_provider

    def get_by_id(self, venue_id: int) -> VenueSummary | None:
        session = self._session_provider()
        query = select(*_SUMMARY_COLUMNS).where(VenueModel.id == venue_id)
        result = session.execute(query)
        row = result.mappings().one_or_none()
        if row is None:
            return None

        return VenueSummary(**row)

    def get_by_ids(self, venue_ids: list[int]) -> dict[int, VenueSummary]:
        unique_ids = list(dict.fromkeys(venue_ids))
        if not unique_ids:
            return {}

        session = self._session_provider()
        summaries: dict[int, VenueSummary] = {}
        for offset in range(0, len(unique_ids), _BATCH_SIZE):
            batch = unique_ids[offset : offset + _BATCH_SIZE]
            query = select(*_SUMMARY_COLUMNS).where(VenueModel.id.in_(batch))
            result = session.execute(query)
            rows = result.mappings()
            for row in rows:
                summary = VenueSummary(**row)
                summaries[summary.id] = summary
        return summaries
