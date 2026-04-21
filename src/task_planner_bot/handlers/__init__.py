"""Task planner bot handlers."""

from aiogram import Dispatcher

from task_planner_bot.handlers.start import router as start_router


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start_router)


__all__ = ["register_handlers"]
