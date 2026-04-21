"""Ozon bot handlers.

Router layout (one submodule per feature area):

    handlers/
        start.py        # /start, welcome flow
        registration.py # seller onboarding (API keys, performance creds)
        profile.py      # profile view and edit
        settings.py     # notifications, time zone
        reviews.py      # review auto-reply templates
        bidder.py       # advertising auto-bidder controls
        reports.py      # finance / warehouse / calculation reports
        tasks.py        # task-planner integration
        admin.py        # admin-only commands

All periodic workloads (review polling, bidder adjustments, report
generation) live in :mod:`worker.tasks` and run under Celery Beat.
"""

from aiogram import Dispatcher

from ozon_bot.handlers.start import router as start_router


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start_router)


__all__ = ["register_handlers"]
