"""Per-user Redis-backed throttling middleware.

When multiple bot replicas share one Redis (which is the normal horizontal-
scaling setup), the throttler has to be *shared* — an in-process counter
would allow N×limit traffic for N replicas. This middleware uses the atomic
Lua script in :class:`RedisRateLimiter`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from helpers_core.cache import RedisRateLimiter
from helpers_core.logging import get_logger
from helpers_core.telemetry.metrics import TELEGRAM_UPDATES

logger = get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(
        self,
        limiter: RedisRateLimiter,
        *,
        bot_name: str,
        throttle_message: str = "Слишком часто. Подождите немного и попробуйте снова.",
    ) -> None:
        super().__init__()
        self._limiter = limiter
        self._bot_name = bot_name
        self._throttle_message = throttle_message

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        decision = await self._limiter.hit(f"u:{user_id}")
        if decision.allowed:
            return await handler(event, data)

        TELEGRAM_UPDATES.labels(bot=self._bot_name, outcome="throttled").inc()
        logger.info(
            "throttled_user", user_id=user_id, current=decision.current, limit=decision.limit
        )
        await self._notify_user(event)
        return None

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        from_user = getattr(event, "from_user", None)
        return getattr(from_user, "id", None)

    async def _notify_user(self, event: TelegramObject) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(self._throttle_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self._throttle_message, show_alert=False)
        except Exception:
            logger.debug("failed_to_notify_throttled_user", exc_info=True)
