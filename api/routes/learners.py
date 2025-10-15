from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, get_current_user, admin_or_teacher_required
from api.schemas.learners import (
    LearnerListResponse,
    LearnerResponse,
    CreateLearnerFromChatIdRequest,
    UpdateLearnerNotificationsRequest,
)
from database import crud

router = APIRouter()


@router.get("", response_model=LearnerListResponse)
async def list_all_learners(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LearnerListResponse:
    learners = await crud.fetch_all_learners(session)
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
    user=Depends(admin_or_teacher_required),
) -> LearnerResponse:
    """Create a new learner from Telegram chat_id"""
    learner = await crud.create_learner_from_chat_id(
        session,
        chat_id=request.chat_id,
        display_name=request.display_name,
        notes=request.notes,
        notifications_enabled=request.notifications_enabled,
    )
    await session.flush()
    await session.refresh(learner, attribute_names=["bot_user"])
    
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
    user=Depends(admin_or_teacher_required),
) -> LearnerResponse:
    """Enable or disable notifications for a learner"""
    learner = await crud.get_learner(session, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    await crud.update_learner(
        session,
        learner,
        notifications_enabled=request.notifications_enabled,
    )
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
    )
