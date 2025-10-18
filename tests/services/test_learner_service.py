import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from services import learner_service
from tests import factories


@pytest.mark.asyncio
async def test_list_all_learners(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, display_name="Learner DTO")
    await db_session.flush()
    learners = await learner_service.get_all_learners(db_session, current_tenant)

    assert len(learners) == 1
    assert learners[0].id == learner.id
    assert learners[0].display_name == "Learner DTO"