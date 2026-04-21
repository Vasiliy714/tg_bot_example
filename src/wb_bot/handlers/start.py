"""``/start`` — entry point and user bootstrap.

This is the minimum handler shown end-to-end to demonstrate the wiring:
DI-injected SQLAlchemy session, repository usage, typed response. All
future handlers follow the same pattern.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from helpers_core.domain import UserRepository
from helpers_core.logging import get_logger

router = Router(name="wb_bot.start")
logger = get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Create-or-update the user and greet them."""
    if message.from_user is None:
        return

    users = UserRepository(session)
    user = await users.get_or_create(
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    logger.info("wb_user_started", user_db_id=user.id, tg_id=user.tg_id)

    await message.answer(
        "<b>Добро пожаловать в WB Helper.</b>\n\n"
        "Это обновлённый бот на новой платформе. "
        "Добавьте магазин командой <code>/add_store</code>, чтобы начать."
    )
