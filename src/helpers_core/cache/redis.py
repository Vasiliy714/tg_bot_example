"""Shared async Redis client.

A single connection pool is created per process. Reusing it across the whole
service (FSM storage, throttling, ad-hoc cache) is both faster and avoids
exhausting Redis' ``maxclients``.
"""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from helpers_core.config import Settings, get_settings

_client: Redis | None = None


def get_redis(settings: Settings | None = None) -> Redis:
    """Return the shared Redis client, building it on first use."""
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = from_url(
            settings.redis.redis_url,
            encoding="utf-8",
            decode_responses=False,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    """Close the Redis client (call on graceful shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
