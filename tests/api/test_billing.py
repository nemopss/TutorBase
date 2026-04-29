from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from services import billing_service, yookassa_service
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


@pytest.mark.asyncio
async def test_billing_checkout_creates_yookassa_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_request(method, path, *, json=None, idempotence_key=None):
        assert method == "POST"
        assert path == "/payments"
        assert idempotence_key
        assert json["amount"] == {"value": "349.00", "currency": "RUB"}
        assert json["capture"] is True
        assert json["metadata"]["tenant_id"] == str(current_tenant.tenant_id)
        assert json["metadata"]["plan_code"] == billing_service.PLAN_BASIC
        return {
            "id": "test-payment-id",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/test"},
        }

    monkeypatch.setattr(yookassa_service, "_request_yookassa", fake_request)
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/billing/checkout",
        json={"plan_code": billing_service.PLAN_BASIC, "billing_period": "month"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "payment_id": "test-payment-id",
        "status": "pending",
        "confirmation_url": "https://yoomoney.ru/checkout/payments/test",
        "amount_due": "349.00",
        "billing_action": "new",
    }


@pytest.mark.asyncio
async def test_billing_checkout_prorates_upgrade(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch: pytest.MonkeyPatch,
):
    fixed_now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    period_start = fixed_now - timedelta(days=15)
    period_end = fixed_now + timedelta(days=15)
    await billing_service.grant_subscription(
        db_session,
        current_tenant.tenant_id,
        plan_code=billing_service.PLAN_BASIC,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
        actor_user_id=None,
        notes="active basic subscription",
    )
    await db_session.commit()
    monkeypatch.setattr(billing_service, "utc_now", lambda: fixed_now)

    async def fake_request(method, path, *, json=None, idempotence_key=None):
        assert json["amount"] == {"value": "474.50", "currency": "RUB"}
        assert json["metadata"]["billing_action"] == "upgrade"
        assert json["metadata"]["previous_plan_code"] == billing_service.PLAN_BASIC
        assert json["metadata"]["credit_amount"] == "174.50"
        assert json["metadata"]["charged_amount"] == "474.50"
        assert json["metadata"]["period_end"] == period_end.isoformat()
        return {
            "id": "upgrade-payment-id",
            "status": "pending",
            "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/upgrade"},
        }

    monkeypatch.setattr(yookassa_service, "_request_yookassa", fake_request)
    headers, _ = await get_auth_headers(db_session, current_tenant)

    preview_response = await client.post(
        "/api/v1/billing/checkout/preview",
        json={"plan_code": billing_service.PLAN_PRO, "billing_period": "month"},
        headers=headers,
    )
    checkout_response = await client.post(
        "/api/v1/billing/checkout",
        json={"plan_code": billing_service.PLAN_PRO, "billing_period": "month"},
        headers=headers,
    )

    assert preview_response.status_code == 200
    assert preview_response.json()["billing_action"] == "upgrade"
    assert preview_response.json()["amount_due"] == "474.50"
    assert preview_response.json()["credit_amount"] == "174.50"
    assert checkout_response.status_code == 200
    assert checkout_response.json()["amount_due"] == "474.50"
    assert checkout_response.json()["billing_action"] == "upgrade"


@pytest.mark.asyncio
async def test_billing_checkout_rejects_downgrade_during_active_paid_period(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    now = datetime.now(timezone.utc)
    await billing_service.grant_subscription(
        db_session,
        current_tenant.tenant_id,
        plan_code=billing_service.PLAN_PRO,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        actor_user_id=None,
        notes="active pro subscription",
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/billing/checkout/preview",
        json={"plan_code": billing_service.PLAN_BASIC, "billing_period": "month"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "тариф ниже" in response.json()["detail"]


@pytest.mark.asyncio
async def test_yookassa_upgrade_webhook_keeps_existing_period_end(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch: pytest.MonkeyPatch,
):
    fixed_now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    period_start = fixed_now - timedelta(days=15)
    period_end = fixed_now + timedelta(days=15)
    await billing_service.grant_subscription(
        db_session,
        current_tenant.tenant_id,
        plan_code=billing_service.PLAN_BASIC,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
        actor_user_id=None,
        notes="active basic subscription",
    )
    await db_session.commit()
    payment_id = "upgrade-payment-id"

    async def fake_get_payment(payment_id_arg: str):
        assert payment_id_arg == payment_id
        return {
            "id": payment_id,
            "status": "succeeded",
            "paid": True,
            "amount": {"value": "474.50", "currency": "RUB"},
            "metadata": {
                "tenant_id": str(current_tenant.tenant_id),
                "plan_code": billing_service.PLAN_PRO,
                "billing_period": "month",
                "billing_action": "upgrade",
                "duration_days": "30",
                "charged_amount": "474.50",
                "full_amount": "649.00",
                "credit_amount": "174.50",
                "period_start": fixed_now.isoformat(),
                "period_end": period_end.isoformat(),
                "previous_plan_code": billing_service.PLAN_BASIC,
            },
        }

    monkeypatch.setattr(yookassa_service, "get_payment", fake_get_payment)

    response = await client.post(
        "/api/v1/billing/yookassa/webhook",
        json={
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": payment_id},
        },
    )

    assert response.status_code == 200
    subscription = await billing_service.get_subscription(db_session, current_tenant.tenant_id)
    assert subscription.plan_code == billing_service.PLAN_PRO
    assert subscription.provider_payment_id == payment_id
    assert subscription.current_period_end == period_end


@pytest.mark.asyncio
async def test_yookassa_payment_succeeded_webhook_activates_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch: pytest.MonkeyPatch,
):
    payment_id = "test-payment-id"

    async def fake_get_payment(payment_id_arg: str):
        assert payment_id_arg == payment_id
        return {
            "id": payment_id,
            "status": "succeeded",
            "paid": True,
            "amount": {"value": "349.00", "currency": "RUB"},
            "metadata": {
                "tenant_id": str(current_tenant.tenant_id),
                "plan_code": billing_service.PLAN_BASIC,
                "billing_period": "month",
                "duration_days": "30",
            },
        }

    monkeypatch.setattr(yookassa_service, "get_payment", fake_get_payment)

    response = await client.post(
        "/api/v1/billing/yookassa/webhook",
        json={
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": payment_id},
        },
    )

    assert response.status_code == 200
    subscription = await billing_service.get_subscription(db_session, current_tenant.tenant_id)
    assert subscription is not None
    assert subscription.plan_code == billing_service.PLAN_BASIC
    assert subscription.status == billing_service.SUBSCRIPTION_STATUS_ACTIVE
    assert subscription.provider == billing_service.PROVIDER_YOOKASSA
    assert subscription.provider_payment_id == payment_id
    assert subscription.current_period_end is not None
    period_end = subscription.current_period_end

    duplicate_response = await client.post(
        "/api/v1/billing/yookassa/webhook",
        json={
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": payment_id},
        },
    )

    assert duplicate_response.status_code == 200
    duplicate_subscription = await billing_service.get_subscription(db_session, current_tenant.tenant_id)
    assert duplicate_subscription.current_period_end == period_end
