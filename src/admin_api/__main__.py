"""Uvicorn launcher for the admin API.

Using ``uvicorn.Config`` + ``uvicorn.Server`` lets us share the event loop
with background tasks if needed. In Docker we prefer multiple single-worker
containers over ``workers > 1`` — that plays better with signal handling
and horizontal scaling.
"""

from __future__ import annotations

import sys

import uvicorn

from helpers_core.config import get_settings


def main() -> None:
    if sys.platform != "win32":
        try:
            import uvloop

            uvloop.install()
        except ImportError:
            pass

    settings = get_settings()
    uvicorn.run(
        "admin_api.app:create_app",
        factory=True,
        host=settings.admin_api.host,
        port=settings.admin_api.port,
        workers=1,
        loop="uvloop" if sys.platform != "win32" else "asyncio",
        access_log=False,
        server_header=False,
        date_header=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
