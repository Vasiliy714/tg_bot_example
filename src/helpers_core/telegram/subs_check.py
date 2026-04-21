"""Channel-subscription gate shared across all bots.

A single reusable implementation with:

* a Redis-cached ``getChatMember`` result (TTL 10 minutes) — keyboard
  clicks and message handlers can call this liberally without generating
  a Telegram API request every time;
* safe handling of channels the bot is not an admin of (returns
  ``False`` instead of raising), so the UI degrades gracefully.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis

from helpers_core.logging import get_logger

logger = get_logger(__name__)

_ALLOWED_STATUSES: frozenset[str] = frozenset({"creator", "administrator", "member", "restricted"})
_NEGATIVE_STATUSES: frozenset[str] = frozenset({"left", "kicked"})


class SubscriptionChecker:
    """Check that a user is subscribed to a Telegram channel / chat.

    Args:
        bot: aiogram ``Bot`` instance used to call ``getChatMember``.
        redis: shared Redis client for caching.
        cache_ttl_seconds: how long to cache positive and negative results.
    """

    def __init__(
        self,
        bot: Bot,
        redis: Redis,
        *,
        cache_ttl_seconds: int = 600,
    ) -> None:
        self._bot = bot
        self._redis = redis
        self._cache_ttl = cache_ttl_seconds

    async def is_subscribed(self, chat_id: int | str, user_id: int) -> bool:
        """Return whether ``user_id`` is a member of ``chat_id``."""
        cache_key = f"subs:{chat_id}:{user_id}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return cached == b"1"

        try:
            member = await self._bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            subscribed = (
                member.status in _ALLOWED_STATUSES and member.status not in _NEGATIVE_STATUSES
            )
        except TelegramAPIError as exc:
            logger.warning("subs_check_failed", chat_id=chat_id, user_id=user_id, error=str(exc))
            return False

        await self._redis.set(cache_key, b"1" if subscribed else b"0", ex=self._cache_ttl)
        return subscribed
