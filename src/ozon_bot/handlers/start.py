"""/start — bootstrap user record and greet."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from helpers_core.domain import UserRepository
from helpers_core.logging import get_logger

router = Router(name="ozon_bot.start")
logger = get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    users = UserRepository(session)
    user = await users.get_or_create(
        tg_id=message.from_user.id, username=message.from_user.username
    )
    logger.info("ozon_user_started", user_db_id=user.id, tg_id=user.tg_id)
    await message.answer(
        "<b>Добро пожаловать в Ozon Helper.</b>\n\n"
        "Добавьте магазин командой <code>/add_store</code>, чтобы начать."
    )
