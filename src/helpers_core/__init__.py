"""Helpers Platform shared core library.

This package is the single source of truth for cross-cutting concerns used by
every service in the monorepo: configuration, logging, database access,
security primitives, HTTP and Telegram infrastructure, marketplace API
clients, Celery wiring and domain models.

Public submodules are imported lazily to keep startup cost minimal and to
avoid import cycles between services.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
