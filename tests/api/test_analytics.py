from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database.models import Payment
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_analytics_overview_aggregates_revenue_workload_and_risks(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    period_start = now - timedelta(days=1)
    period_end = now + timedelta(days=7)

    learner = await factories.create_learner(db_session, display_name="Analytics Student")
    learner.lesson_rate = Decimal("1000")
    package = await factories.create_package(
        db_session,
        learner=learner,
        title="Analytics Package",
        status="active",
        total_lessons=3,
    )
    package.price = Decimal("3000")

    completed = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=now - timedelta(hours=4),
        status="completed",
        duration_minutes=90,
    )
    planned = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=now + timedelta(days=2),
        status="scheduled",
        duration_minutes=60,
    )
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=now + timedelta(hours=2),
        status="cancelled",
        duration_minutes=60,
    )
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=period_start - timedelta(days=2),
        status="completed",
        duration_minutes=60,
    )

    inactive_learner = await factories.create_learner(db_session, display_name="No Future Student")
    inactive_learner.lesson_rate = Decimal("900")

    rule = await factories.create_reminder_rule(db_session, package=package, lesson=completed)
    await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=planned,
        status="delivered",
        scheduled_at=now + timedelta(hours=3),
    )
    await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=planned,
        status="failed",
        scheduled_at=now + timedelta(hours=4),
    )

    db_session.add(
        Payment(
            tenant_id=1,
            learner=learner,
            package=package,
            amount=Decimal("1000"),
            currency="RUB",
            paid_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get(
        "/api/v1/analytics/overview",
        headers=headers,
        params={
            "from_date": period_start.isoformat(),
            "to_date": period_end.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    summary = payload["summary"]

    assert summary["active_learners"] == 2
    assert summary["completed_lessons"] == 1
    assert summary["planned_lessons"] == 1
    assert summary["cancelled_lessons"] == 1
    assert summary["completed_hours"] == 1.5
    assert summary["planned_hours"] == 1.0
    assert Decimal(str(summary["cash_revenue"])) == Decimal("1000")
    assert Decimal(str(summary["earned_revenue"])) == Decimal("1000")
    assert Decimal(str(summary["planned_revenue"])) == Decimal("1000")
    assert Decimal(str(summary["outstanding_revenue"])) == Decimal("2000")
    assert summary["notification_delivery_rate"] == 0.5

    assert payload["comparisons"]["completed_lessons"]["previous"] == 1
    assert payload["notifications"]["total_failed"] == 1

    learner_rows = {item["learner_name"]: item for item in payload["learners"]}
    assert "no_future_lessons" in learner_rows["No Future Student"]["risk_flags"]
    assert "outstanding_balance" in learner_rows["Analytics Student"]["risk_flags"]

    package_rows = {item["package_title"]: item for item in payload["packages"]}
    assert package_rows["Analytics Package"]["ends_soon"] is True
    assert "ending_soon" in package_rows["Analytics Package"]["risk_flags"]

    insight_codes = {item["code"] for item in payload["insights"]}
    assert "no_future_learners" in insight_codes
    assert "notification_failures" in insight_codes


@pytest.mark.asyncio
async def test_analytics_overview_requires_tenant_context(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers, _ = await get_auth_headers(
        db_session,
        CurrentTenant(tenant_id=None, is_super_admin=True, tenant=None),
        role="admin",
    )
    now = datetime.now(timezone.utc)

    response = await client.get(
        "/api/v1/analytics/overview",
        headers=headers,
        params={
            "from_date": (now - timedelta(days=7)).isoformat(),
            "to_date": now.isoformat(),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant context required for analytics endpoints"
