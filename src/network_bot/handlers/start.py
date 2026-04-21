"""/start for the networking bot."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from helpers_core.domain import UserRepository

router = Router(name="network_bot.start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    users = UserRepository(session)
    await users.get_or_create(tg_id=message.from_user.id, username=message.from_user.username)
    await message.answer("Networking bot is online.")
