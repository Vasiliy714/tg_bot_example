"""Domain layer: SQLAlchemy ORM models and repositories.

Wildberries and Ozon share a single set of tables — :class:`User`,
:class:`Magazine` (seller storefront), :class:`Subscription` and
:class:`Task`. The ``marketplace`` discriminator on :class:`Magazine`
tells the application which API client to use, and marketplace-specific
credential columns live on the same row.
"""

from helpers_core.domain.models import (
    Magazine,
    MarketplaceKind,
    Subscription,
    Task,
    TaskKind,
    User,
)
from helpers_core.domain.repositories import (
    MagazineRepository,
    SubscriptionRepository,
    TaskRepository,
    UserRepository,
)

__all__ = [
    "Magazine",
    "MagazineRepository",
    "MarketplaceKind",
    "Subscription",
    "SubscriptionRepository",
    "Task",
    "TaskKind",
    "TaskRepository",
    "User",
    "UserRepository",
]
