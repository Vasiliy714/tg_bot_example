"""Async runtime helpers for Celery tasks.

Kept separate from :mod:`worker.tasks` so the task definitions stay thin
and the business logic is unit-testable without Celery infrastructure.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

from aiogram import Bot

from helpers_core.config import get_settings
from helpers_core.db import session_scope
from helpers_core.domain import TaskRepository
from helpers_core.domain.models import TaskKind
from helpers_core.logging import get_logger

logger = get_logger(__name__)


def _current_minute() -> time:
    """Current wall-clock hour+minute (seconds stripped)."""
    now = datetime.now(tz=UTC).time()
    return time(hour=now.hour, minute=now.minute)


async def dispatch_due_task_notifications() -> int:
    """Fetch tasks due this minute and send Telegram notifications.

    Separate bot tokens are attempted in order (WB / Ozon / task-planner /
    network) — the first one with a non-empty token wins. In production you
    would normally store ``bot_name`` on the task and route accordingly.

    Returns the count of actually delivered messages.
    """
    settings = get_settings()
    bot_token = _pick_bot_token(settings)
    if not bot_token:
        logger.warning("no_bot_token_configured_for_notifications")
        return 0

    now_t = _current_minute()
    bot = Bot(token=bot_token)
    sent = 0
    try:
        async with session_scope() as session:
            tasks = await TaskRepository(session).list_due(now_t)
            for task in tasks:
                if not _task_should_fire(task, now=datetime.now(tz=UTC)):
                    continue
                try:
                    await bot.send_message(
                        chat_id=task.chat_id,
                        text=(
                            f"<b>{task.title}</b>\n{task.description}".strip()
                            if task.description
                            else f"<b>{task.title}</b>"
                        ),
                        parse_mode="HTML",
                    )
                    sent += 1
                    if task.kind == TaskKind.ONCE:
                        await TaskRepository(session).deactivate(task.id)
                except Exception:
                    logger.exception("task_notification_failed", task_id=task.id)
    finally:
        await bot.session.close()
    return sent


def _pick_bot_token(settings: object) -> str:
    for attr in (
        "task_planner_bot_token",
        "wb_bot_token",
        "ozon_bot_token",
        "network_bot_token",
    ):
        raw = getattr(settings.telegram, attr).get_secret_value()  # type: ignore[attr-defined]
        if raw:
            return raw  # type: ignore[no-any-return]
    return ""


def _task_should_fire(task: object, *, now: datetime) -> bool:
    """Apply frequency rules (daily / weekly / monthly / once)."""
    kind = getattr(task, "kind", None)
    data = getattr(task, "data", {}) or {}

    if kind == TaskKind.DAILY:
        return True
    if kind == TaskKind.WEEKLY:
        return (now.weekday() + 1) == int(data.get("day_of_week", 0))
    if kind == TaskKind.MONTHLY:
        return now.day == int(data.get("day_of_month", 0))
    if kind == TaskKind.ONCE:
        return now.date().isoformat() == data.get("date", "")
    return False
