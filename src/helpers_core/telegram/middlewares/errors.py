"""Top-level error logging and user-facing error message.

aiogram lets us attach a dispatcher-level handler for uncaught exceptions —
this middleware complements that by always logging with correlation id and
reporting a short, user-friendly message (the exact error details stay in
the logs).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message, TelegramObject

from helpers_core.logging import get_logger
from helpers_core.telemetry.metrics import TELEGRAM_UPDATES

logger = get_logger(__name__)


class ErrorLoggingMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        bot_name: str,
        user_facing_message: str = (
            "Произошла внутренняя ошибка. Мы уже получили сообщение и разберёмся. Попробуйте позже."
        ),
    ) -> None:
        super().__init__()
        self._bot_name = bot_name
        self._user_facing_message = user_facing_message

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            result = await handler(event, data)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            # These are expected: user blocked the bot, tried to edit a
            # message that is no longer editable, etc. Log at INFO.
            TELEGRAM_UPDATES.labels(bot=self._bot_name, outcome="telegram_error").inc()
            logger.info("telegram_api_error", error=str(exc))
            return None
        except Exception:
            TELEGRAM_UPDATES.labels(bot=self._bot_name, outcome="error").inc()
            logger.exception("handler_crashed")
            await self._notify_user(event)
            raise
        else:
            TELEGRAM_UPDATES.labels(bot=self._bot_name, outcome="ok").inc()
            return result

    async def _notify_user(self, event: TelegramObject) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(self._user_facing_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(self._user_facing_message, show_alert=True)
        except Exception:
            logger.debug("failed_to_notify_on_error", exc_info=True)
