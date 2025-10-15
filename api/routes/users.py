from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import admin_required, get_session
from api.schemas.users import UpdateUserRoleRequest, UserItem, UserListResponse
from database import crud

router = APIRouter()


def _serialize_user(user) -> UserItem:
    return UserItem(
        id=user.id,
        display_name=user.display_name,
        username=user.username,
        telegram_id=user.telegram_id,
        role=user.role,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_required),
) -> UserListResponse:
    users = await crud.list_users(session)
    return UserListResponse(users=[_serialize_user(item) for item in users])


@router.patch("/{user_id}/role", response_model=UserItem)
async def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> UserItem:
    user = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = await crud.update_user_login_metadata(session, user, role=payload.role)
    return _serialize_user(user)
