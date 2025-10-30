from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_required, get_current_tenant, CurrentTenant, get_current_user
from api.schemas import UserResponse, UserRoleUpdateRequest, PaginationParams, PaginatedResponse
from database import crud
from database.models import User
from utils.cache import invalidate_cache

router = APIRouter()


def _to_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user information"""
    return _to_response(current_user)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> PaginatedResponse[UserResponse]:
    users, total = await crud.list_users_paginated(
        session,
        current_tenant,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    items = [_to_response(u) for u in users]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> UserResponse:
    """Update user role.
    
    Invalidates user cache after role change to ensure permission checks
    use updated role immediately.
    """
    user = await crud.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = payload.role
    session.add(user)
    await session.commit()
    
    # Invalidate user cache for this user (critical for permission checks)
    await invalidate_cache("users:_get_user_cached:*")
    
    return _to_response(user)