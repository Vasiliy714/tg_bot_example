"""Shared aiogram bot factory.

Every bot service builds its ``Bot`` and ``Dispatcher`` identically — this
module centralises that so we don't drift (e.g. one bot uses JSON storage,
another MemoryStorage, a third forgets middlewares entirely).
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from helpers_core.cache import RedisRateLimiter, get_redis
from helpers_core.config import Settings, get_settings
from helpers_core.db import get_sessionmaker
from helpers_core.telegram.middlewares import (
    DbSessionMiddleware,
    ErrorLoggingMiddleware,
    StructlogMiddleware,
    ThrottlingMiddleware,
)


@dataclass(slots=True, frozen=True)
class BotBundle:
    """Everything a bot service needs to start polling.

    The bundle makes lifecycle explicit: callers close the bot's session
    on shutdown, and the redis / sessionmaker are managed by the caller
    (they're shared with other parts of the process).
    """

    bot: Bot
    dispatcher: Dispatcher
    redis: Redis


def build_bot_bundle(
    *,
    token: str,
    bot_name: str,
    settings: Settings | None = None,
    rate_limit: int = 5,
    rate_window_seconds: int = 2,
) -> BotBundle:
    """Build a fully-wired ``Bot`` + ``Dispatcher`` pair.

    Args:
        token: Telegram bot token (from settings).
        bot_name: identifier used as a Prometheus / log label (``"wb_bot"``…).
        rate_limit / rate_window_seconds: per-user throttling parameters.
    """
    settings = settings or get_settings()
    if not token:
        raise ValueError(f"Bot token for '{bot_name}' is not configured")

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    redis = get_redis(settings)
    storage = RedisStorage(redis=redis, state_ttl=3600, data_ttl=3600)
    dispatcher = Dispatcher(storage=storage)

    limiter = RedisRateLimiter(
        redis,
        limit=rate_limit,
        window_seconds=rate_window_seconds,
        key_prefix=f"rl:{bot_name}:",
    )

    dispatcher.update.outer_middleware(StructlogMiddleware(bot_name=bot_name))
    dispatcher.update.outer_middleware(ErrorLoggingMiddleware(bot_name=bot_name))
    dispatcher.update.outer_middleware(ThrottlingMiddleware(limiter, bot_name=bot_name))
    dispatcher.update.outer_middleware(DbSessionMiddleware(get_sessionmaker(settings)))

    return BotBundle(bot=bot, dispatcher=dispatcher, redis=redis)
