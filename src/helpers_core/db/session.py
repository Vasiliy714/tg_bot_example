"""Async engine & session factory.

Key design points:

* A single engine per process, built lazily; creating a second engine
  defeats pooling and doubles the connection count.
* ``AsyncAdaptedQueuePool`` with configurable size — chosen over
  ``NullPool`` because the latter reconnects on every request, which is
  unacceptable under load.
* ``pool_pre_ping`` to survive silently-dropped connections (firewalls,
  Postgres restarts) without surfacing them as user-visible errors.
* ``expire_on_commit=False`` so that model instances remain usable after
  ``session.commit()`` in request handlers.
* A :func:`session_scope` context manager is provided for scripts and
  tests; in services, sessions are injected via the middleware layer
  (aiogram) or FastAPI dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from helpers_core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.db.dsn,
        echo=settings.db_pool.echo,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=settings.db_pool.pool_size,
        max_overflow=settings.db_pool.max_overflow,
        pool_timeout=settings.db_pool.pool_timeout,
        pool_recycle=settings.db_pool.pool_recycle,
        pool_pre_ping=True,
        # asyncpg already handles statement cache; default is fine.
        future=True,
    )


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return the module-level async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = _build_engine(settings or get_settings())
    return _engine


def get_sessionmaker(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return the module-level sessionmaker."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


@asynccontextmanager
async def session_scope(
    settings: Settings | None = None,
) -> AsyncIterator[AsyncSession]:
    """Convenience context manager for ad-hoc scripts and tests.

    It takes care of the commit / rollback dance around the ``yield`` so
    that callers only need ``async with session_scope() as session: ...``.
    In production handlers, use the DI-provided session instead.
    """

    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def dispose_engine() -> None:
    """Dispose of the engine (call on graceful shutdown)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
