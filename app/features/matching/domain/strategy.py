"""Compatibility imports; implementation lives in the flat feature package."""

from app.features.matching.strategy import (
    CAPACITY,
    MAX_RANK_SPREAD,
    build_suggestion,
    fee_for,
    find_group,
    group_is_valid,
    policy_allows,
)

__all__ = [
    "CAPACITY",
    "MAX_RANK_SPREAD",
    "policy_allows",
    "fee_for",
    "group_is_valid",
    "find_group",
    "build_suggestion",
]
