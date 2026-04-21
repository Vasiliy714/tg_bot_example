"""Network bot entrypoint — identical lifecycle to the other bots."""

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
from network_bot.handlers import register_handlers

logger = get_logger(__name__)
BOT_NAME = "network_bot"


async def _run() -> None:
    settings = get_settings()
    configure_logging(BOT_NAME, settings)
    bundle = build_bot_bundle(
        token=settings.telegram.network_bot_token.get_secret_value(),
        bot_name=BOT_NAME,
    )
    register_handlers(bundle.dispatcher)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            start_metrics_server(settings.metrics.host, settings.metrics.port)
        )
        polling = asyncio.create_task(
            bundle.dispatcher.start_polling(
                bundle.bot,
                allowed_updates=bundle.dispatcher.resolve_used_update_types(),
                handle_signals=False,
            ),
            name="network-bot-polling",
        )
        try:
            await stop_event.wait()
        finally:
            await bundle.dispatcher.stop_polling()
            await polling
            await bundle.bot.session.close()
            await close_redis()
            await dispose_engine()


def main() -> None:
    if sys.platform != "win32":
        try:
            import uvloop

            uvloop.install()
        except ImportError:
            pass
    asyncio.run(_run())


if __name__ == "__main__":
    main()
