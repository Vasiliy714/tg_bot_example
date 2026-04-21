"""Async HTTP client facade for outbound calls.

Wrapping :mod:`aiohttp` in a thin class gives us one place to implement:

* connection-pool sizing (``TCPConnector``) — critical under bursty traffic;
* unified JSON handling via :mod:`orjson` (2–3× faster than stdlib);
* retries on idempotent methods with exponential backoff + full jitter
  (tenacity) — the marketplaces return 502/503 under load surprisingly often;
* circuit-breaker short-circuiting to protect our own service during
  downstream outages;
* Prometheus instrumentation on every request (status, latency, method);
* structlog context with the target host and path for traceability.

All marketplace clients in :mod:`helpers_core.marketplaces` are built on top
of this class.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self

import aiohttp
import orjson
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from helpers_core.config import Settings, get_settings
from helpers_core.http.circuit_breaker import CircuitBreaker
from helpers_core.logging import get_logger
from helpers_core.telemetry.metrics import (
    HTTP_CLIENT_IN_FLIGHT,
    HTTP_CLIENT_LATENCY,
    HTTP_CLIENT_REQUESTS,
)

logger = get_logger(__name__)


class HttpError(RuntimeError):
    """Base class for client-side HTTP failures (network / timeout)."""


class HttpResponseError(HttpError):
    """Raised for non-2xx responses that we refuse to retry further."""

    def __init__(self, status: int, body: str, url: str) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.body = body
        self.url = url


@dataclass(slots=True, frozen=True)
class HttpClientConfig:
    """Tunable parameters for :class:`HttpClient`.

    The defaults come from the application settings; callers can override
    them per-client (e.g. a slower API may need a longer timeout).
    """

    base_url: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    max_connections: int = 100
    max_connections_per_host: int = 20
    default_headers: dict[str, str] = field(default_factory=dict)
    service_label: str = "default"

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        **overrides: Any,
    ) -> HttpClientConfig:
        settings = settings or get_settings()
        base = dict(
            timeout_seconds=settings.http.timeout_seconds,
            max_retries=settings.http.max_retries,
            max_connections=settings.http.max_connections,
            max_connections_per_host=settings.http.max_connections_per_host,
        )
        base.update(overrides)
        return cls(**base)  # type: ignore[arg-type]


# HTTP status codes considered transient and eligible for automatic retry.
_RETRYABLE_STATUS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

# We retry only idempotent methods by default. POST retries can cause
# duplicate side-effects on the server (e.g. creating two ads).
_IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class HttpClient:
    """High-level async HTTP client.

    Usage:
        async with HttpClient(HttpClientConfig(base_url="https://...")) as http:
            data = await http.get_json("/foo", params={"bar": 1})

    The client is also safe to use as a long-lived dependency: call
    :meth:`start` during application startup and :meth:`close` on shutdown
    (the ``docker-compose`` stack does exactly that via lifespan hooks).
    """

    def __init__(
        self,
        config: HttpClientConfig | None = None,
        *,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._config = config or HttpClientConfig()
        self._breaker = breaker or CircuitBreaker(name=self._config.service_label)
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._session is not None:
            return
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
        connector = aiohttp.TCPConnector(
            limit=self._config.max_connections,
            limit_per_host=self._config.max_connections_per_host,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,
        )
        self._session = aiohttp.ClientSession(
            base_url=self._config.base_url,
            timeout=timeout,
            connector=connector,
            headers=self._config.default_headers,
            json_serialize=lambda obj: orjson.dumps(obj).decode("utf-8"),
            raise_for_status=False,
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------ core

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> aiohttp.ClientResponse:
        """Perform an HTTP request with retries, breaker and metrics.

        Returns the raw response still open for reading (consumers call
        :meth:`aiohttp.ClientResponse.json` / :meth:`.read`). Use
        :meth:`get_json` / :meth:`post_json` when you just need JSON.
        """
        if self._session is None:
            raise RuntimeError("HttpClient not started; call `await client.start()`")

        method_upper = method.upper()
        retryable = method_upper in _IDEMPOTENT_METHODS

        async def _do_call() -> aiohttp.ClientResponse:
            assert self._session is not None
            HTTP_CLIENT_IN_FLIGHT.labels(service=self._config.service_label).inc()
            with HTTP_CLIENT_LATENCY.labels(
                service=self._config.service_label,
                method=method_upper,
            ).time():
                try:
                    response = await self._session.request(
                        method_upper,
                        url,
                        params=params,
                        json=json,
                        data=data,
                        headers=headers,
                    )
                finally:
                    HTTP_CLIENT_IN_FLIGHT.labels(service=self._config.service_label).dec()

            HTTP_CLIENT_REQUESTS.labels(
                service=self._config.service_label,
                method=method_upper,
                status=str(response.status),
            ).inc()
            if response.status in _RETRYABLE_STATUS and retryable:
                body = await response.text()
                response.release()
                raise HttpResponseError(response.status, body, str(response.url))
            return response

        retrying = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(self._config.max_retries + 1 if retryable else 1),
            wait=wait_exponential_jitter(initial=0.2, max=5.0),
            retry=retry_if_exception_type(
                (
                    HttpResponseError,
                    aiohttp.ClientConnectionError,
                    aiohttp.ServerTimeoutError,
                    asyncio.TimeoutError,
                )
            ),
        )

        try:
            async for attempt in retrying:
                with attempt:
                    return await self._breaker.call(_do_call)
        except RetryError as exc:
            raise HttpError(f"Exhausted retries for {method_upper} {url}") from exc

        raise HttpError(f"Unreachable: {method_upper} {url}")  # pragma: no cover

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.request("GET", url, params=params, headers=headers)
        return await self._read_json(response)

    async def post_json(
        self,
        url: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.request("POST", url, json=json, headers=headers)
        return await self._read_json(response)

    @staticmethod
    async def _read_json(response: aiohttp.ClientResponse) -> Any:
        try:
            if response.status >= 400:
                body = await response.text()
                raise HttpResponseError(response.status, body, str(response.url))
            raw = await response.read()
            return orjson.loads(raw) if raw else None
        finally:
            response.release()
