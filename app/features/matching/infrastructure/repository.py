"""Compatibility imports; implementation lives in the flat feature package."""

from app.features.matching.repository import (
    SqlAlchemyMatchingRepository,
    to_matching_record,
)

__all__ = [
    "SqlAlchemyMatchingRepository",
    "to_matching_record",
]
