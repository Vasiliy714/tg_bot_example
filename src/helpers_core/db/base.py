"""Declarative base with an explicit naming convention.

Alembic autogeneration produces stable, predictable constraint names only if
SQLAlchemy is told how to name indexes, foreign keys, etc. Without this,
migrations will churn between environments and merges become painful.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

# Reference: https://alembic.sqlalchemy.org/en/latest/naming.html
naming_convention: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


class Base(AsyncAttrs, DeclarativeBase):
    """Project-wide SQLAlchemy 2.x base.

    * :class:`AsyncAttrs` makes lazy-loaded attributes awaitable, which
      composes nicely with async sessions and avoids ``MissingGreenlet``
      errors in handlers.
    * The explicit :data:`metadata` drives the naming convention above.
    """

    metadata = metadata
