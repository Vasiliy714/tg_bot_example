"""Minimal async circuit breaker.

The marketplace APIs occasionally have outages that last minutes. Without a
breaker, every queued request would pile up on the gateway, blowing our
aiohttp pool and, worse, delaying Telegram updates on unrelated handlers.
The breaker short-circuits calls in the ``open`` state so they fail fast.

States:
    closed      -- traffic flows normally; failures are counted.
    open        -- failure threshold exceeded; calls are refused for
                   ``reset_timeout`` seconds.
    half_open   -- a single probe call is allowed; success closes the
                   breaker, failure re-opens it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class CircuitBreakerOpen(RuntimeError):
    """Raised when the breaker refuses a call because it is open."""


class _State(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class _BreakerState:
    failures: int = 0
    opened_at: float = 0.0
    state: _State = _State.CLOSED


class CircuitBreaker:
    """Async, per-instance circuit breaker.

    Example:
        breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
        try:
            return await breaker.call(lambda: http.get("/ping"))
        except CircuitBreakerOpen:
            return cached_fallback()
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if reset_timeout <= 0:
            raise ValueError("reset_timeout must be positive")

        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._name = name
        self._state = _BreakerState()
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> str:
        return self._state.state.value

    async def _on_success(self) -> None:
        async with self._lock:
            self._state = _BreakerState()

    async def _on_failure(self) -> None:
        async with self._lock:
            self._state.failures += 1
            if self._state.failures >= self._failure_threshold:
                self._state.state = _State.OPEN
                self._state.opened_at = time.monotonic()

    async def _precheck(self) -> None:
        async with self._lock:
            if self._state.state is _State.OPEN:
                if time.monotonic() - self._state.opened_at >= self._reset_timeout:
                    self._state.state = _State.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"circuit '{self._name}' is open (failures={self._state.failures})"
                    )

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute ``func`` (zero-arg async callable) under the breaker.

        The return type is preserved via ``TypeVar`` so that callers get the
        same ``T`` the wrapped coroutine produces.
        """
        await self._precheck()
        try:
            result = await func()
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result
