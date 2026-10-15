"""Declarative SQLAlchemy base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all Phase 1 ORM models."""
