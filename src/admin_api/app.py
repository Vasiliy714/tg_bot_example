"""FastAPI application factory.

Exposes:

* ``/healthz`` — liveness, always 200 when the process is alive;
* ``/readyz``  — readiness, verifies DB + Redis connectivity;
* ``/metrics`` — Prometheus metrics (same registry as every other service);
* ``/api/v1/*`` — administrative CRUD (users, magazines, subscriptions).

The lifespan hook creates and disposes the DB engine and Redis client once
per process. This avoids per-request creation and keeps ``admin_api``
consistent with the bot services' resource lifecycle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from admin_api.api.routes import health, users
from helpers_core.cache import close_redis, get_redis
from helpers_core.config import get_settings
from helpers_core.db import dispose_engine, get_engine
from helpers_core.logging import configure_logging, get_logger
from helpers_core.telemetry.metrics import metrics_app

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging("admin_api", settings)
    # eager init so readiness probe can reuse the same singletons
    get_engine(settings)
    get_redis(settings)
    logger.info("admin_api_starting", release=settings.app_release, env=settings.app_env.value)
    try:
        yield
    finally:
        await close_redis()
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Helpers Platform — Admin API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
        default_response_class=_orjson_response(),
    )
    app.include_router(health.router)
    app.include_router(users.router, prefix="/api/v1")
    app.mount("/metrics", metrics_app)  # type: ignore[arg-type]
    return app


def _orjson_response() -> type:
    """Use orjson for responses — noticeably faster than stdlib json."""
    from fastapi.responses import ORJSONResponse

    return ORJSONResponse
