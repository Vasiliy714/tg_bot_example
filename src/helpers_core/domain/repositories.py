"""Thin repositories around the ORM models.

Each repository does one thing: issue SQL and return ORM entities (or
primitive data). All Telegram- or HTTP-facing formatting stays out of
this layer and lives in handlers / services — which keeps repositories
reusable from FastAPI, Celery tasks and admin scripts alike.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers_core.domain.models import (
    Magazine,
    MarketplaceKind,
    Subscription,
    Task,
    TaskKind,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, tg_id: int, *, username: str | None = None) -> User:
        user = await self._session.scalar(select(User).where(User.tg_id == tg_id))
        if user is not None:
            if username and user.username != username:
                user.username = username
            return user
        user = User(tg_id=tg_id, username=username)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        return await self._session.scalar(select(User).where(User.tg_id == tg_id))


class MagazineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, magazine: Magazine) -> Magazine:
        self._session.add(magazine)
        await self._session.flush()
        return magazine

    async def list_for_user(
        self,
        user_id: int,
        marketplace: MarketplaceKind | None = None,
    ) -> Sequence[Magazine]:
        stmt = select(Magazine).where(Magazine.user_id == user_id)
        if marketplace is not None:
            stmt = stmt.where(Magazine.marketplace == marketplace)
        result = await self._session.scalars(stmt.order_by(Magazine.title))
        return result.all()


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int, kind: str) -> Subscription | None:
        return await self._session.scalar(
            select(Subscription).where(Subscription.user_id == user_id, Subscription.kind == kind)
        )

    async def set_balance(self, user_id: int, kind: str, balance: int) -> Subscription:
        existing = await self.get(user_id, kind)
        if existing is None:
            existing = Subscription(user_id=user_id, kind=kind, balance=balance)
            self._session.add(existing)
        else:
            existing.balance = balance
        await self._session.flush()
        return existing


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        user_id: int,
        chat_id: int,
        title: str,
        description: str,
        kind: TaskKind,
        data: dict,
        notification_time: time,
    ) -> Task:
        task = Task(
            user_id=user_id,
            chat_id=chat_id,
            title=title,
            description=description,
            kind=kind,
            data=data,
            notification_time=notification_time,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def list_due(self, now_time: time) -> Sequence[Task]:
        """Tasks that fire at ``now_time`` (hour + minute match).

        The worker calls this each minute; comparing only H:M is enough
        because the scheduler ticks at minute granularity anyway.
        """
        stmt = select(Task).where(
            Task.is_active.is_(True),
            Task.notification_time == now_time,
        )
        result = await self._session.scalars(stmt)
        return result.all()

    async def deactivate(self, task_id: int) -> None:
        task = await self._session.get(Task, task_id)
        if task is not None:
            task.is_active = False
            await self._session.flush()
