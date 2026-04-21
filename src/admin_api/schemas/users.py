"""Pydantic schemas for the Users admin API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tg_id: int
    username: str | None = None
    time_zone: str | None = None
    created_at: datetime
    updated_at: datetime
