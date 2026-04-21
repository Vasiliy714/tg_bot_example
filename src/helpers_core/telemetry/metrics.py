"""Shared Prometheus metrics and the metrics endpoint helper.

We keep every metric in a single module so that importing it twice does not
accidentally register two collectors (Prometheus raises ``Duplicated
timeseries`` when that happens). Service-specific metrics should live in the
service package itself, but follow the same pattern (module-level
definitions).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from prometheus_client import (
    REGISTRY as _DEFAULT_REGISTRY,
)
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Use the default registry so that :func:`prometheus_client.make_asgi_app`
# (and our own ASGI app below) picks everything up without extra wiring.
REGISTRY: CollectorRegistry = _DEFAULT_REGISTRY

# ----------------------------------------------------------------------
# HTTP client (used by helpers_core.http.client.HttpClient)
# ----------------------------------------------------------------------

HTTP_CLIENT_REQUESTS: Counter = Counter(
    "http_client_requests_total",
    "Outbound HTTP requests by service, method and status.",
    labelnames=("service", "method", "status"),
)

HTTP_CLIENT_LATENCY: Histogram = Histogram(
    "http_client_request_latency_seconds",
    "Outbound HTTP request latency in seconds.",
    labelnames=("service", "method"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

HTTP_CLIENT_IN_FLIGHT: Gauge = Gauge(
    "http_client_in_flight_requests",
    "Currently in-flight outbound HTTP requests.",
    labelnames=("service",),
)

# ----------------------------------------------------------------------
# Telegram update pipeline
# ----------------------------------------------------------------------

TELEGRAM_UPDATES: Counter = Counter(
    "telegram_updates_total",
    "Telegram updates processed by bot and outcome.",
    labelnames=("bot", "outcome"),
)

TELEGRAM_UPDATE_LATENCY: Histogram = Histogram(
    "telegram_update_latency_seconds",
    "End-to-end latency of a Telegram update handler.",
    labelnames=("bot",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# ----------------------------------------------------------------------
# Celery tasks
# ----------------------------------------------------------------------

CELERY_TASK_LATENCY: Histogram = Histogram(
    "celery_task_latency_seconds",
    "Celery task execution latency.",
    labelnames=("task", "status"),
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 300, 600),
)


# ----------------------------------------------------------------------
# ASGI metrics endpoint
# ----------------------------------------------------------------------


async def metrics_app(scope: dict, receive: object, send: object) -> None:  # type: ignore[override]
    """Minimal ASGI app exposing ``/metrics``.

    Mounted inside FastAPI as well as used standalone for bot processes that
    don't expose an HTTP API. Hand-rolled (instead of
    :func:`prometheus_client.make_asgi_app`) so we can keep the registry
    explicit in tests.
    """
    assert scope["type"] == "http"
    payload = generate_latest(REGISTRY)
    send_cb = send  # type: ignore[assignment]
    await send_cb(  # type: ignore[misc]
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain; version=0.0.4; charset=utf-8")],
        }
    )
    await send_cb(  # type: ignore[misc]
        {"type": "http.response.body", "body": payload, "more_body": False}
    )


@asynccontextmanager
async def start_metrics_server(host: str, port: int) -> AsyncIterator[None]:
    """Start a standalone metrics server (no FastAPI needed).

    Uses uvicorn so we don't pull in a second ASGI stack. The server runs
    in a background task and is cleanly stopped on context exit.
    """
    import uvicorn

    config = uvicorn.Config(
        app=metrics_app,
        host=host,
        port=port,
        log_level="warning",
        lifespan="off",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(), name="metrics-server")
    try:
        yield
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=5)
