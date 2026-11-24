"""Compatibility imports; implementation lives in the flat feature package."""

from app.features.matching.routers.requests import (
    create_matching_router,
    to_matching_input,
    to_matching_response,
)

__all__ = [
    "create_matching_router",
    "to_matching_input",
    "to_matching_response",
]
