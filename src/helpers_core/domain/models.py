"""ORM models.

Cross-marketplace and normalised:

* one :class:`User` record per Telegram user, not per marketplace;
* one :class:`Magazine` table covers both Wildberries and Ozon,
  discriminated by the ``marketplace`` column;
* API tokens are stored as :class:`EncryptedString` — encryption happens
  once, at the ORM boundary, so callers never deal with ciphertext;
* all tables have proper foreign keys, indexes and ``created_at`` /
  ``updated_at`` timestamps for audit and efficient admin queries.
"""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers_core.db import Base, EncryptedString


class MarketplaceKind(StrEnum):
    WILDBERRIES = "wildberries"
    OZON = "ozon"


class TaskKind(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONCE = "once"


class _TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(_TimestampMixin, Base):
    """Telegram user profile, shared between all bots."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    time_zone: Mapped[str | None] = mapped_column(String(64))

    magazines: Mapped[list[Magazine]] = relationship(back_populates="user", lazy="noload")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user", lazy="noload")


class Magazine(_TimestampMixin, Base):
    """A seller's storefront on a specific marketplace.

    For Wildberries only ``wb_api_token`` is used; for Ozon all four
    credential fields are used. Unused columns remain ``NULL``.
    """

    __tablename__ = "magazines"
    __table_args__ = (
        UniqueConstraint("user_id", "title", "marketplace", name="uq_magazines_user_title_mp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    marketplace: Mapped[MarketplaceKind] = mapped_column(String(32), index=True)

    # Wildberries
    wb_api_token: Mapped[str | None] = mapped_column(EncryptedString(length=2048))

    # Ozon — split credentials
    ozon_client_id: Mapped[str | None] = mapped_column(EncryptedString(length=512))
    ozon_api_key: Mapped[str | None] = mapped_column(EncryptedString(length=512))
    ozon_perf_client_id: Mapped[str | None] = mapped_column(EncryptedString(length=512))
    ozon_perf_secret: Mapped[str | None] = mapped_column(EncryptedString(length=2048))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    user: Mapped[User] = relationship(back_populates="magazines")


class Subscription(_TimestampMixin, Base):
    """Paid feature subscription for a user.

    Each row is a single feature (general reports, bidder, review auto-reply);
    ``expires_at`` is NULL for free tier.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_subscriptions_user_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    balance: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    user: Mapped[User] = relationship(back_populates="subscriptions")


class Task(_TimestampMixin, Base):
    """Reminder / task entity shared across every bot in the platform.

    A single table powers the standalone task-planner bot as well as the
    task-planner features embedded into the WB and Ozon bots.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "title",
            "kind",
            "notification_time",
            name="uq_tasks_user_title_kind_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    kind: Mapped[TaskKind] = mapped_column(String(16))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    notification_time: Mapped[time] = mapped_column(Time)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
