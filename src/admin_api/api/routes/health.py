"""Liveness / readiness probes.

These endpoints are deliberately tiny and *never* do heavy work — in
Kubernetes / GitLab environments they are polled every few seconds, so
anything expensive here would be a self-inflicted outage.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from admin_api.api.deps import DbSession
from helpers_core.cache import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness — returns as soon as the event loop is running."""
    return {"status": "alive"}


@router.get("/readyz")
async def readyz(session: DbSession) -> dict[str, str]:
    """Readiness — verifies DB and Redis are usable."""
    await session.execute(text("SELECT 1"))
    await get_redis().ping()
    return {"status": "ready"}
