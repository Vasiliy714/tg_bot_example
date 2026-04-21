"""Structured JSON logging based on structlog.

Every service wires logging identically by calling :func:`configure_logging`
once at startup. This yields JSON in production and colourised output in
development, and attaches a ``correlation_id`` context variable to every
record so that a single Telegram update can be traced end-to-end across
handlers, DB queries, HTTP calls and Celery tasks.
"""

from helpers_core.logging.setup import (
    bind_correlation_id,
    clear_correlation_id,
    configure_logging,
    get_logger,
    new_correlation_id,
)

__all__ = [
    "bind_correlation_id",
    "clear_correlation_id",
    "configure_logging",
    "get_logger",
    "new_correlation_id",
]
