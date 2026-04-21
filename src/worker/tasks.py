"""Celery tasks.

Each task is a thin async function wrapped so that heavy workloads —
review polling, bidder adjustments, report generation, task-planner
notifications — run outside of the bot polling loop, on horizontally
scalable worker nodes.

Async inside Celery is bridged via :func:`_run_async`: Celery itself is
synchronous, so we create a dedicated event loop per task invocation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from helpers_core.logging import get_logger
from helpers_core.messaging import celery_app
from worker.runtime import dispatch_due_task_notifications

logger = get_logger(__name__)

T = TypeVar("T")


def _run_async(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run an async coroutine inside a sync Celery task.

    A fresh loop per call is wasteful; in production we'd pin one loop per
    worker via a ``celeryd_init`` signal handler. The simple path is
    sufficient for the extracted jobs at hand.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()


@celery_app.task(name="worker.tasks.health_tick", ignore_result=True)
def health_tick() -> str:
    """Cheapest possible task — used as a live heartbeat for Beat."""
    return datetime.now(tz=UTC).isoformat()


@celery_app.task(
    name="worker.tasks.dispatch_task_notifications",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    ignore_result=True,
)
def dispatch_task_notifications(self) -> int:  # type: ignore[no-untyped-def]
    """Deliver due task reminders (runs every minute from beat schedule).

    Returns the number of notifications sent (useful for metrics).
    """

    async def _run() -> int:
        return await dispatch_due_task_notifications()

    sent = _run_async(_run)
    logger.info("task_notifications_sent", count=sent, task_id=self.request.id)
    return sent


# Add the task-planner notification dispatch to beat.
celery_app.conf.beat_schedule.update(
    {
        "dispatch-task-notifications-every-minute": {
            "task": "worker.tasks.dispatch_task_notifications",
            "schedule": 60.0,
        },
    }
)
