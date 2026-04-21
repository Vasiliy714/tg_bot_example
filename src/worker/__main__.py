"""Entrypoints for Celery worker and beat.

Two separate processes are preferred over ``celery worker -B`` in
production (distinct failure domains, independent scaling).
"""

from __future__ import annotations

from helpers_core.config import get_settings
from helpers_core.logging import configure_logging
from helpers_core.messaging import celery_app


def _configure() -> None:
    configure_logging("worker", get_settings())


def main() -> None:
    """Celery worker: ``helpers-worker``."""
    _configure()
    celery_app.worker_main(argv=["worker", "--loglevel=INFO", "--concurrency=4"])


def beat() -> None:
    """Celery beat: ``helpers-beat``."""
    _configure()
    celery_app.start(argv=["beat", "--loglevel=INFO"])


if __name__ == "__main__":
    main()
