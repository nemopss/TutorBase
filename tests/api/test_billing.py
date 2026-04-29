from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from services import billing_service
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_billing_current_defaults_to_start_plan(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    await factories.create_learner(db_session, display_name="A")
    await factories.create_learner(db_session, display_name="B")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get("/api/v1/billing/current", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "start"
    assert body["plan_name"] == "Старт"
    assert body["active_learners_limit"] == 3
    assert body["active_learners_count"] == 2
    assert body["can_create_learner"] is True
    assert body["notifications_allowed"] is True


@pytest.mark.asyncio
async def test_start_plan_blocks_fourth_active_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    for index in range(3):
        await factories.create_learner(db_session, display_name=f"Learner {index}")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/learners",
        json={"display_name": "Fourth", "notifications_enabled": True},
        headers=headers,
    )

    assert response.status_code == 402
    assert "Пока нет места для активного ученика" in response.json()["detail"]


@pytest.mark.asyncio
async def test_start_plan_over_limit_disables_notifications(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    await billing_service.ensure_subscription(
        db_session,
        current_tenant.tenant_id,
        notes="start plan over limit test",
    )
    for index in range(4):
        await factories.create_learner(db_session, display_name=f"Learner {index}")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get("/api/v1/billing/current", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "start"
    assert body["active_learners_count"] == 4
    assert body["active_learners_limit"] == 3
    assert body["notifications_allowed"] is False


@pytest.mark.asyncio
async def test_expired_paid_subscription_keeps_data_but_disables_notifications_over_start_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    now = datetime.now(timezone.utc)
    for index in range(4):
        await factories.create_learner(db_session, display_name=f"Learner {index}")
    await billing_service.grant_subscription(
        db_session,
        current_tenant.tenant_id,
        plan_code=billing_service.PLAN_PRO,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=now - timedelta(days=40),
        current_period_end=now - timedelta(days=1),
        actor_user_id=None,
        notes="expired test subscription",
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    list_response = await client.get("/api/v1/learners", headers=headers)
    billing_response = await client.get("/api/v1/billing/current", headers=headers)

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 4
    assert billing_response.status_code == 200
    body = billing_response.json()
    assert body["plan_code"] == "start"
    assert body["active_learners_count"] == 4
    assert body["is_over_limit"] is True
    assert body["can_create_learner"] is False
    assert body["notifications_allowed"] is False
    assert body["billing_restriction_reason"] == "subscription_expired_over_free_limit"


@pytest.mark.asyncio
async def test_active_paid_subscription_uses_paid_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    now = datetime.now(timezone.utc)
    for index in range(4):
        await factories.create_learner(db_session, display_name=f"Learner {index}")
    await billing_service.grant_subscription(
        db_session,
        current_tenant.tenant_id,
        plan_code=billing_service.PLAN_BASIC,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        actor_user_id=None,
        notes="active test subscription",
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get("/api/v1/billing/current", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "basic"
    assert body["active_learners_limit"] == 10
    assert body["can_create_learner"] is True
    assert body["notifications_allowed"] is True
