"""Middleware that injects a short-lived :class:`AsyncSession` into handlers.

Rationale:

* Every update gets its own session — short-lived, no cross-handler leaks.
* Commits happen on successful return; rollbacks on exceptions.
* Handlers receive the session via a named keyword argument (default:
  ``session``), so DI is explicit and type-checkable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        key: str = "session",
    ) -> None:
        super().__init__()
        self._sessionmaker = sessionmaker
        self._key = key

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._sessionmaker() as session:
            data[self._key] = session
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()
                return result
