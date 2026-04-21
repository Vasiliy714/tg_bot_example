"""Prometheus telemetry primitives.

Services import :mod:`helpers_core.telemetry.metrics` to both define service-
specific metrics and to access the shared instruments used by the HTTP
client, Celery tasks, DB layer, etc.
"""

from helpers_core.telemetry.metrics import (
    CELERY_TASK_LATENCY,
    HTTP_CLIENT_IN_FLIGHT,
    HTTP_CLIENT_LATENCY,
    HTTP_CLIENT_REQUESTS,
    TELEGRAM_UPDATE_LATENCY,
    TELEGRAM_UPDATES,
    metrics_app,
    start_metrics_server,
)

__all__ = [
    "CELERY_TASK_LATENCY",
    "HTTP_CLIENT_IN_FLIGHT",
    "HTTP_CLIENT_LATENCY",
    "HTTP_CLIENT_REQUESTS",
    "TELEGRAM_UPDATES",
    "TELEGRAM_UPDATE_LATENCY",
    "metrics_app",
    "start_metrics_server",
]
