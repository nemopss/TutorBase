from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from services.dto import LearnerDTO


def _build_learner_dto(learner) -> LearnerDTO:
    return LearnerDTO(
        id=learner.id,
        display_name=learner.display_name,
        # добавьте другие поля DTO по мере необходимости
    )


async def list_all_learners(session: AsyncSession) -> list[LearnerDTO]:
    learners = await crud.fetch_all_learners(session)
    return [_build_learner_dto(learner) for learner in learners]


__all__ = ["list_all_learners"]
