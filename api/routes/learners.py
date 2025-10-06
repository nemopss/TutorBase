from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.schemas.learners import LearnerListResponse, LearnerResponse
from services import learner_service

router = APIRouter()


@router.get("", response_model=LearnerListResponse)
async def list_all_learners(
    session: AsyncSession = Depends(get_session),
) -> LearnerListResponse:
    learners = await learner_service.list_all_learners(session)
    return LearnerListResponse(
        items=[LearnerResponse(id=learner.id, display_name=learner.display_name) for learner in learners]
    )
