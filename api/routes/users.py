from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_required,
    get_current_tenant,
    get_current_user,
    get_session,
    is_platform_admin,
)
from api.schemas import UserResponse, UserRoleUpdateRequest, PaginationParams, PaginatedResponse
from api.schemas.learners import LearnerResponse, StudentLearnerResponse
from database import crud
from database.models import User
from utils.cache import invalidate_cache

router = APIRouter()


def _to_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        email=user.email,
        email_verified_at=user.email_verified_at,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_platform_admin=is_platform_admin(user),
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


@router.get("/me/learner", response_model=StudentLearnerResponse)
async def get_current_learner_info(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> StudentLearnerResponse:
    """Get learner profile for current authenticated user.
    
    Finds learner profile linked to user's Telegram ID.
    """
    if not current_user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User is not linked to Telegram"
        )

    bot_user = await crud.get_bot_user_by_chat_id(session, current_user.telegram_id)
    if not bot_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Bot user not found"
        )

    learner = await crud.get_learner_by_bot_user(session, current_tenant, bot_user.id)
    if not learner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Learner profile not found"
        )
        
    return StudentLearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        next_lesson_date=None,
    )


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

    if current_tenant.tenant_id is not None and user.tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access is managed by the ADMINS allowlist",
        )

    if is_platform_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role is managed by the ADMINS allowlist",
        )

    if payload.role != "viewer" and await crud.user_has_active_learner_account_link(session, user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Linked learner accounts cannot be promoted to staff roles. Unlink the learner account first.",
        )

    user.role = payload.role
    session.add(user)
    await session.commit()
    
    # Invalidate user cache for this user (critical for permission checks)
    await invalidate_cache("users:_get_user_cached:*")
    
    return _to_response(user)
