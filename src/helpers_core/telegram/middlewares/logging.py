"""Structured-logging middleware.

Adds a correlation id to structlog's context for the lifetime of an update
and measures end-to-end latency via :data:`TELEGRAM_UPDATE_LATENCY`.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from helpers_core.logging import bind_correlation_id, clear_correlation_id
from helpers_core.logging.setup import get_logger
from helpers_core.telemetry.metrics import TELEGRAM_UPDATE_LATENCY

logger = get_logger(__name__)


class StructlogMiddleware(BaseMiddleware):
    def __init__(self, *, bot_name: str) -> None:
        super().__init__()
        self._bot_name = bot_name

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        correlation_id = bind_correlation_id()
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        chat = getattr(event, "chat", None)
        chat_id = getattr(chat, "id", None)

        logger.info(
            "update_received",
            bot=self._bot_name,
            event_type=event.__class__.__name__,
            user_id=user_id,
            chat_id=chat_id,
        )

        start = time.perf_counter()
        try:
            return await handler(event, data | {"correlation_id": correlation_id})
        finally:
            elapsed = time.perf_counter() - start
            TELEGRAM_UPDATE_LATENCY.labels(bot=self._bot_name).observe(elapsed)
            logger.info("update_processed", elapsed_seconds=round(elapsed, 4))
            clear_correlation_id()
