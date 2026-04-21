"""Users administrative API (read-only in v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from admin_api.api.deps import DbSession, require_admin_token
from admin_api.schemas.users import UserRead
from helpers_core.domain import UserRepository

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin_token)],
)


@router.get("/{tg_id}", response_model=UserRead)
async def get_user(tg_id: int, session: DbSession) -> UserRead:
    user = await UserRepository(session).get_by_tg_id(tg_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user, from_attributes=True)
