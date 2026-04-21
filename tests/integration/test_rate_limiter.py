"""Integration test for the Redis rate limiter.

Requires a running Redis (``docker compose up -d redis``). Skipped in
unit-test runs by the ``integration`` marker.
"""

from __future__ import annotations

import os

import pytest
from redis.asyncio import from_url

from helpers_core.cache import RedisRateLimiter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rate_limiter_allows_then_denies() -> None:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis = from_url(url)
    try:
        limiter = RedisRateLimiter(redis, limit=3, window_seconds=2, key_prefix="test-rl:")
        results = [await limiter.hit("integration-key") for _ in range(5)]
    finally:
        await redis.delete("test-rl:integration-key")
        await redis.aclose()

    assert [r.allowed for r in results] == [True, True, True, False, False]
