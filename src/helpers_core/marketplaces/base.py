"""Common abstractions for marketplace clients."""

from __future__ import annotations

from typing import Protocol, Self, runtime_checkable


@runtime_checkable
class MarketplaceClient(Protocol):
    """Lifecycle shape every marketplace client must implement.

    Used by services to manage client lifetime generically (they keep a
    registry keyed by seller id and shut them down on exit).
    """

    async def start(self) -> None: ...
    async def close(self) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *args: object) -> None: ...
