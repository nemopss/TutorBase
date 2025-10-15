import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from services import learner_service
from tests import factories


@pytest.mark.asyncio
async def test_list_all_learners(db_session: AsyncSession):
    learner = await factories.create_learner(db_session, display_name="Learner DTO")
    learners = await learner_service.list_all_learners(db_session)

    assert len(learners) == 1
    assert learners[0].id == learner.id
    assert learners[0].display_name == "Learner DTO"
