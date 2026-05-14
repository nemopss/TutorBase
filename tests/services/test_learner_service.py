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


@pytest.mark.asyncio
async def test_update_learner_notifications_refreshes_schedules_on_change(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch,
):
    learner = await factories.create_learner(db_session, notifications_enabled=False)
    await db_session.flush()
    calls = []

    async def fake_refresh(session, tenant, refreshed_learner, *, reason):
        calls.append(
            {
                "session": session,
                "tenant": tenant,
                "learner_id": refreshed_learner.id,
                "reason": reason,
            }
        )

    monkeypatch.setattr(
        learner_service,
        "refresh_learner_notification_schedules",
        fake_refresh,
    )

    updated = await learner_service.update_learner_notifications(
        db_session,
        current_tenant,
        learner_id=learner.id,
        notifications_enabled=True,
    )

    assert updated is not None
    assert updated.notifications_enabled is True
    assert calls == [
        {
            "session": db_session,
            "tenant": current_tenant,
            "learner_id": learner.id,
            "reason": "learner_notifications_changed",
        }
    ]
