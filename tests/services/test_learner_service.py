import pytest

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database.models import Payment
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


@pytest.mark.asyncio
async def test_delete_learner_archives_and_preserves_financial_history(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    payment = Payment(
        tenant_id=current_tenant.tenant_id,
        learner=learner,
        package=package,
        amount=Decimal("1500.00"),
        currency="RUB",
        paid_at=datetime.now(timezone.utc),
    )
    db_session.add(payment)
    await db_session.flush()
    learner_id = learner.id
    package_id = package.id
    payment_id = payment.id

    async def fake_refresh(*args, **kwargs):
        return None

    monkeypatch.setattr(
        learner_service,
        "refresh_learner_notification_schedules",
        fake_refresh,
    )

    assert await learner_service.delete_learner(
        db_session,
        current_tenant,
        learner_id=learner_id,
    )

    archived = await db_session.get(type(learner), learner_id)
    assert archived is not None
    assert archived.archived_at is not None
    assert archived.notifications_enabled is False
    assert await db_session.get(type(package), package_id) is not None
    assert await db_session.get(Payment, payment_id) is not None

    active = await learner_service.get_all_learners(db_session, current_tenant)
    assert all(item.id != learner_id for item in active)
