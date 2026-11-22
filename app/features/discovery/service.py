from dataclasses import replace

from app.domain.errors import DomainError
from app.domain.ports import Clock, UnitOfWork
from app.features.discovery.contracts import (
    DiscoveryRepository,
    Page,
    SessionFilter,
    VenueFilter,
)


class DiscoveryService:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        discovery_repo: DiscoveryRepository,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._discovery = discovery_repo

    def search_venues(self, filt: VenueFilter) -> Page:
        with self._uow.read():
            return self._discovery.find_venues(filt)

    def search_sessions(self, filt: SessionFilter, viewer_id: int | None) -> Page:
        if filt.host_me and viewer_id is None:
            raise DomainError(
                "UNAUTHORIZED",
                "Đăng nhập để xem các kèo của bạn.",
            )

        with self._uow.read():
            now = self._clock.now()

            if filt.host_me:
                filt = replace(
                    filt,
                    now=now,
                    host_user_id=viewer_id,
                    only_listable=False,
                    only_available=False,
                )
            else:
                filt = replace(filt, now=now, host_user_id=None)
            return self._discovery.find_sessions(filt)
