"""Tests for the async circuit breaker."""

from __future__ import annotations

import asyncio

import pytest

from helpers_core.http.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


@pytest.mark.asyncio
async def test_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=1.0)

    async def failing() -> None:
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(failing)

    assert breaker.state == "open"
    with pytest.raises(CircuitBreakerOpen):
        await breaker.call(failing)


@pytest.mark.asyncio
async def test_half_open_then_closes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)

    async def bad() -> None:
        raise RuntimeError("boom")

    async def good() -> int:
        return 42

    with pytest.raises(RuntimeError):
        await breaker.call(bad)
    assert breaker.state == "open"

    await asyncio.sleep(0.06)
    assert await breaker.call(good) == 42
    assert breaker.state == "closed"
