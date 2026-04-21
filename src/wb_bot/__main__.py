"""Entrypoint for the Wildberries bot.

Usage:
    $ wb-bot

What it does:

* installs ``uvloop`` on supported platforms (free throughput boost);
* configures structured logging;
* builds an aiogram :class:`Bot` + :class:`Dispatcher` with all shared
  middlewares via :func:`helpers_core.telegram.bootstrap.build_bot_bundle`;
* registers handlers from :mod:`wb_bot.handlers`;
* starts a Prometheus endpoint in background;
* runs long-polling with graceful shutdown on ``SIGINT`` / ``SIGTERM``.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import AsyncExitStack

from helpers_core.cache import close_redis
from helpers_core.config import get_settings
from helpers_core.db import dispose_engine
from helpers_core.logging import configure_logging, get_logger
from helpers_core.telegram.bootstrap import build_bot_bundle
from helpers_core.telemetry import start_metrics_server
from wb_bot.handlers import register_handlers

logger = get_logger(__name__)
BOT_NAME = "wb_bot"


def _install_uvloop() -> None:
    if sys.platform == "win32":
        return
    try:
        import uvloop

        uvloop.install()
    except ImportError:  # pragma: no cover — uvloop is optional
        pass


async def _run() -> None:
    settings = get_settings()
    configure_logging(BOT_NAME, settings)

    bundle = build_bot_bundle(
        token=settings.telegram.wb_bot_token.get_secret_value(),
        bot_name=BOT_NAME,
    )
    register_handlers(bundle.dispatcher)

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            start_metrics_server(settings.metrics.host, settings.metrics.port)
        )
        logger.info("bot_starting", bot=BOT_NAME, release=settings.app_release)
        polling = asyncio.create_task(
            bundle.dispatcher.start_polling(
                bundle.bot,
                allowed_updates=bundle.dispatcher.resolve_used_update_types(),
                handle_signals=False,
            ),
            name="wb-bot-polling",
        )
        try:
            await stop_event.wait()
        finally:
            await bundle.dispatcher.stop_polling()
            await polling
            await bundle.bot.session.close()
            await close_redis()
            await dispose_engine()
            logger.info("bot_stopped", bot=BOT_NAME)


def main() -> None:
    _install_uvloop()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
