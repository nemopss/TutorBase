from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_session,
    admin_or_teacher_required,
    get_current_tenant,
    CurrentTenant,
)
from api.schemas.learners import (
    LearnerListResponse,
    LearnerResponse,
    CreateLearnerFromChatIdRequest,
    UpdateLearnerNotificationsRequest,
)
from services import learner_service

router = APIRouter()


@router.get("", response_model=LearnerListResponse)
async def list_all_learners(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> LearnerListResponse:
    """Lists all learners for the current tenant."""
    learners = await learner_service.get_all_learners(session, current_tenant)
    items = []
    for learner in learners:
        chat_id = learner.bot_user.chat_id if learner.bot_user else None
        items.append(
            LearnerResponse(
                id=learner.id,
                display_name=learner.display_name,
                notifications_enabled=learner.notifications_enabled,
                chat_id=chat_id,
            )
        )
    return LearnerListResponse(items=items)


@router.post("", response_model=LearnerResponse, status_code=201)
async def create_learner_from_chat_id(
    request: CreateLearnerFromChatIdRequest,
    session: AsyncSession = Depends(get_session),
    # We still need role check, but get tenant context separately
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> LearnerResponse:
    """Create a new learner from Telegram chat_id."""
    learner = await learner_service.create_learner_from_chat_id(
        session,
        current_tenant,
        chat_id=request.chat_id,
        display_name=request.display_name,
        notes=request.notes,
        notifications_enabled=request.notifications_enabled,
    )
    
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=learner.bot_user.chat_id if learner.bot_user else None,
    )


@router.patch("/{learner_id}/notifications", response_model=LearnerResponse)
async def update_learner_notifications(
    learner_id: int,
    request: UpdateLearnerNotificationsRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> LearnerResponse:
    """Enable or disable notifications for a learner."""
    learner = await learner_service.update_learner_notifications(
        session,
        current_tenant,
        learner_id=learner_id,
        notifications_enabled=request.notifications_enabled,
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
    )