"""Celery worker / beat process.

Runs every heavy periodic job of the platform — review polling, report
generation, advertising auto-bidding, task-planner notifications — so
the bot processes stay responsive to user input. See :mod:`worker.tasks`
for individual tasks and their beat schedule.
"""

from helpers_core.messaging import celery_app

__all__ = ["celery_app"]
