"""Compatibility imports; implementation lives in the flat feature package."""

from app.features.matching.matching_request_writer import (
    SqlAlchemyMatchingRequestWriter,
)

__all__ = [
    "SqlAlchemyMatchingRequestWriter",
]
