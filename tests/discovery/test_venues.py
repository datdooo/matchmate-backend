from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.features.discovery.contracts import VenueFilter, VenueRecord, Page
from app.features.discovery.schemas import VenueQuery, VenueView


def test_venue_query_defaults():
    query = VenueQuery()

    assert query.district_code is None
    assert query.limit == 20
    assert query.offset == 0


def test_venue_query_accepts_filter_and_pagination():
    query = VenueQuery(district_code="Q1", limit=10, offset=20)

    assert query.district_code == "Q1"
    assert query.limit == 10
    assert query.offset == 20


@pytest.mark.parametrize(
    "payload",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"unknown_filter": "value"},
    ],
)
def test_venue_query_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        VenueQuery(**payload)


def test_venue_view_can_validate_orm_like_object():
    row = SimpleNamespace(
        id=1,
        name="Court A",
        address="Example street",
        district_code="Q1",
        is_active=True,
    )

    result = VenueView.model_validate(row)

    assert result.id == 1
    assert result.name == "Court A"
    assert result.district_code == "Q1"
    assert result.is_active is True


def test_venue_contracts_keep_pagination_metadata():
    venue = VenueRecord(
        id=1,
        name="Court A",
        address="Example street",
        district_code="Q1",
        is_active=True,
    )
    page = Page(items=[venue], total=5, limit=1, offset=2)
    filt = VenueFilter(district_code="Q1", limit=1, offset=2)

    assert page.items == [venue]
    assert page.total == 5
    assert (page.limit, page.offset) == (filt.limit, filt.offset)
