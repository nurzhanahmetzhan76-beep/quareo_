"""Declarative base and cross-DB UUID type for all ORM models."""

import uuid

from sqlalchemy import String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class UUIDType(TypeDecorator):
    """Platform-agnostic UUID column type.

    Uses PostgreSQL's native UUID when available,
    falls back to CHAR(32) for SQLite (tests).
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value.hex
            return uuid.UUID(value).hex
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(32))


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""
    pass
