"""Task planner Telegram bot.

The bot process is responsible only for handling user input (creating,
editing and listing tasks). Scheduling and delivery live in the Celery
Beat worker (see :mod:`worker.tasks.dispatch_task_notifications`), which
scans the ``tasks`` table every minute and dispatches notifications via
the bot token. This keeps the bot stateless and horizontally scalable,
and decouples notification delivery from bot liveness.
"""
