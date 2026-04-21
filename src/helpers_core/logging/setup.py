"""structlog configuration shared by every service."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.types import EventDict, Processor

from helpers_core.config import Settings, get_settings

_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """Generate a short correlation id (first 16 hex chars of a UUID4).

    Short enough to read in logs, wide enough to avoid realistic collisions.
    """

    return uuid.uuid4().hex[:16]


def bind_correlation_id(correlation_id: str | None = None) -> str:
    """Attach (or create) a correlation id to the structlog context.

    Returns the effective id so that callers can echo it in responses /
    Telegram error messages for easier support.
    """

    cid = correlation_id or new_correlation_id()
    _correlation_id_var.set(cid)
    bind_contextvars(correlation_id=cid)
    return cid


def clear_correlation_id() -> None:
    _correlation_id_var.set(None)
    clear_contextvars()


def _add_correlation_id(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Ensure every record carries the current correlation id if one is set."""
    cid = _correlation_id_var.get()
    if cid is not None and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid
    return event_dict


def _add_service(service_name: str) -> Processor:
    def processor(_: Any, __: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service_name)
        return event_dict

    return processor


def configure_logging(
    service_name: str,
    settings: Settings | None = None,
) -> None:
    """Configure both stdlib logging and structlog once at process start.

    Args:
        service_name: logical service identifier (``wb_bot``, ``admin_api``…).
            It is added to every log record as ``service`` field, which is
            indispensable when all services ship logs to a shared collector.
        settings: injected settings (mostly for tests); defaults to the
            cached application settings.
    """

    settings = settings or get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )
    # Dampen noisy third-party loggers — we still want warnings from them.
    for noisy in ("aiogram.event", "asyncio", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        _add_service(service_name),
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format.value == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a ``structlog`` logger bound to ``name`` (usually ``__name__``)."""
    return structlog.get_logger(name)  # type: ignore[return-value]
