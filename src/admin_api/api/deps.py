"""FastAPI dependencies for DI (DB session, admin check, etc.)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from helpers_core.config import Settings, get_settings
from helpers_core.db import get_sessionmaker


async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a short-lived session, auto-committing on success."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


DbSession = Annotated[AsyncSession, Depends(db_session)]


def _settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(_settings_dep)]


def require_admin_token(
    settings: SettingsDep,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Simple header-based auth for admin endpoints.

    Acceptable for an internal tool; replace with OAuth2 / mTLS when
    exposing the API to third parties.
    """
    expected = settings.security.keys[0]  # reuse the primary Fernet key as a shared secret
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
