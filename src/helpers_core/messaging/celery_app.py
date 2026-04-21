"""Celery application factory.

Heavy periodic workloads (review polling, report generation, advertising
auto-bidding, task-planner notifications) run on Celery rather than
inside the bot polling loops. Celery + RabbitMQ give us:

* horizontal scaling — run ``helpers-worker`` on multiple nodes;
* observability — failed jobs land in the DLQ, stats go to Prometheus;
* retries and time limits as a config concern, not code;
* an explicit schedule via Celery Beat.
"""

from __future__ import annotations

import time

from celery import Celery
from celery.signals import task_failure, task_prerun, task_success

from helpers_core.config import Settings, get_settings
from helpers_core.logging import get_logger
from helpers_core.telemetry.metrics import CELERY_TASK_LATENCY

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prometheus instrumentation via Celery signals.
# Capturing start time with a dict keyed by task_id avoids a global lock.
# Handlers are registered eagerly (module-level) so they survive worker
# process fork — registering them inside a function that runs only on
# import would work on the beat/worker entrypoints but miss eager execution.
# ---------------------------------------------------------------------------

_task_start_times: dict[str, float] = {}


@task_prerun.connect
def _on_prerun(task_id: str | None = None, **_: object) -> None:
    if task_id:
        _task_start_times[task_id] = time.perf_counter()


@task_success.connect
def _on_success(sender: object = None, **_: object) -> None:
    task_name = getattr(sender, "name", "unknown")
    request = getattr(sender, "request", None)
    task_id = getattr(request, "id", None) if request else None
    started = _task_start_times.pop(task_id, None) if task_id else None
    if started is not None:
        CELERY_TASK_LATENCY.labels(task=task_name, status="success").observe(
            time.perf_counter() - started
        )


@task_failure.connect
def _on_failure(
    sender: object = None,
    task_id: str | None = None,
    **_: object,
) -> None:
    task_name = getattr(sender, "name", "unknown")
    started = _task_start_times.pop(task_id, None) if task_id else None
    if started is not None:
        CELERY_TASK_LATENCY.labels(task=task_name, status="failure").observe(
            time.perf_counter() - started
        )


def build_celery_app(settings: Settings | None = None) -> Celery:
    """Construct the Celery app.

    Beat schedule is defined here as data — individual modules register
    task functions (``@app.task``) by importing them through the
    :data:`include` list below.
    """
    settings = settings or get_settings()
    app = Celery(
        "helpers",
        broker=settings.rabbit.rabbitmq_url,
        backend=settings.rabbit.celery_result_backend,
        include=["worker.tasks"],
    )

    app.conf.update(
        task_default_queue="default",
        task_serializer="json",
        accept_content=("json",),
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_time_limit=10 * 60,
        task_soft_time_limit=9 * 60,
        worker_max_tasks_per_child=500,
        worker_prefetch_multiplier=4,
        broker_connection_retry_on_startup=True,
        beat_schedule={
            # A minimal default schedule; services add their own via
            # `app.conf.beat_schedule.update(...)` at import time.
            "health-tick": {
                "task": "worker.tasks.health_tick",
                "schedule": 60.0,
            },
        },
    )
    return app


celery_app: Celery = build_celery_app()
