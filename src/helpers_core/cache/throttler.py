"""Atomic, Redis-based sliding-window rate limiter.

Using a Lua script guarantees atomicity even when multiple bot processes
share one Redis — without it you would race between GET and SET and let
bursts through.

The implementation is a fixed-window counter with ``INCR`` + ``EXPIRE``,
which is:

* O(1) per request — no sorted-set cleanup like a true sliding window
  requires, keeping Redis busy time tiny;
* good enough for anti-spam throttling (the exact window boundary drift of
  at most ``window_seconds`` is not meaningful to an abusive user).
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

_LUA_INCR_EXPIRE = """
local current = redis.call('INCR', KEYS[1])
if tonumber(current) == 1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return current
"""


@dataclass(slots=True, frozen=True)
class RateLimitDecision:
    """Result of a single limiter check.

    Attributes:
        allowed: whether the request is under the limit.
        current: number of requests inside the current window after this call.
        limit: configured limit for the window.
    """

    allowed: bool
    current: int
    limit: int


class RedisRateLimiter:
    """Fixed-window rate limiter backed by Redis + Lua.

    Example:
        limiter = RedisRateLimiter(redis, limit=5, window_seconds=2)
        decision = await limiter.hit(f"tg:{user_id}")
        if not decision.allowed:
            return await message.answer("Too many requests.")
    """

    def __init__(
        self,
        redis: Redis,
        limit: int,
        window_seconds: int,
        *,
        key_prefix: str = "rl:",
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._redis = redis
        self._limit = limit
        self._window_ms = window_seconds * 1000
        self._prefix = key_prefix
        # register_script caches the SHA on the client and uses EVALSHA
        self._script = self._redis.register_script(_LUA_INCR_EXPIRE)

    async def hit(self, key: str) -> RateLimitDecision:
        redis_key = f"{self._prefix}{key}"
        current_raw = await self._script(keys=[redis_key], args=[self._window_ms])
        current = int(current_raw)  # type: ignore[arg-type]
        return RateLimitDecision(
            allowed=current <= self._limit,
            current=current,
            limit=self._limit,
        )
