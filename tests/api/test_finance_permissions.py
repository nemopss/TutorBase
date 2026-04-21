from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database.models import Payment
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_viewer_cannot_read_finance_or_payments(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant, role="viewer")

    dashboard_response = await client.get("/api/v1/finance/dashboard", headers=headers)
    debtors_response = await client.get("/api/v1/finance/debtors", headers=headers)
    report_response = await client.get("/api/v1/finance/reports/income", headers=headers)
    export_response = await client.get("/api/v1/finance/reports/income/export", headers=headers)
    payments_response = await client.get("/api/v1/payments", headers=headers)
    learner_finance_response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)

    assert dashboard_response.status_code == 403
    assert debtors_response.status_code == 403
    assert report_response.status_code == 403
    assert export_response.status_code == 403
    assert payments_response.status_code == 403
    assert learner_finance_response.status_code == 403


@pytest.mark.asyncio
async def test_create_payment_rejects_package_from_another_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    other_learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    package.price = Decimal("100.00")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": other_learner.id,
            "package_id": package.id,
            "amount": "50.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Package does not belong to learner"


@pytest.mark.asyncio
async def test_create_payment_rejects_lesson_from_another_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    other_learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": other_learner.id,
            "lesson_id": lesson.id,
            "amount": "50.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Lesson does not belong to learner"


@pytest.mark.asyncio
async def test_create_payment_rejects_lesson_package_mismatch(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    lesson_package = await factories.create_package(db_session, learner=learner, title="Lesson Package")
    selected_package = await factories.create_package(db_session, learner=learner, title="Selected Package")
    lesson = await factories.create_lesson(db_session, package=lesson_package)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": learner.id,
            "package_id": selected_package.id,
            "lesson_id": lesson.id,
            "amount": "50.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Lesson does not belong to package"


@pytest.mark.asyncio
async def test_create_payment_infers_package_from_lesson(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    package.price = Decimal("100.00")
    package.payment_status = "unpaid"
    lesson = await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    package_id = package.id
    lesson_id = lesson.id
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": learner.id,
            "lesson_id": lesson_id,
            "amount": "100.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["package_id"] == package_id
    assert body["lesson_id"] == lesson_id

    await db_session.refresh(package)
    assert package.payment_status == "paid"


@pytest.mark.asyncio
async def test_update_payment_edits_in_place_and_recalculates_package_status(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, status="active")
    package.price = Decimal("100.00")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    create_response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": learner.id,
            "package_id": package.id,
            "amount": "30.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "notes": "first payment",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    payment_id = create_response.json()["id"]

    patch_response = await client.patch(
        f"/api/v1/payments/{payment_id}",
        json={
            "amount": "100.00",
            "notes": "corrected payment",
        },
        headers=headers,
    )

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["amount"] == "100.00"
    assert body["notes"] == "corrected payment"

    await db_session.refresh(package)
    assert package.payment_status == "paid"


@pytest.mark.asyncio
async def test_delete_payment_soft_voids_and_removes_from_finance_totals(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, status="active")
    package.price = Decimal("100.00")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    create_response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": learner.id,
            "package_id": package.id,
            "amount": "100.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    payment_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/payments/{payment_id}", headers=headers)
    assert delete_response.status_code == 204

    payment = await db_session.get(Payment, payment_id)
    assert payment is not None
    assert payment.voided_at is not None

    await db_session.refresh(package)
    assert package.payment_status == "unpaid"

    list_response = await client.get("/api/v1/payments", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0

    finance_response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)
    assert finance_response.status_code == 200
    assert Decimal(str(finance_response.json()["total_paid"])) == Decimal("0")


@pytest.mark.asyncio
async def test_create_payment_rejects_cross_tenant_lesson(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    tenant_2,
):
    foreign_learner = await factories.create_learner(db_session, tenant_id=tenant_2.id)
    foreign_package = await factories.create_package(
        db_session,
        learner=foreign_learner,
        tenant_id=tenant_2.id,
    )
    foreign_lesson = await factories.create_lesson(
        db_session,
        package=foreign_package,
        tenant_id=tenant_2.id,
    )
    local_learner = await factories.create_learner(db_session)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": local_learner.id,
            "lesson_id": foreign_lesson.id,
            "amount": "50.00",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Lesson not found"


@pytest.mark.asyncio
async def test_dashboard_unpaid_count_uses_actual_outstanding(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, status="active")
    package.price = Decimal("100.00")
    package.payment_status = "partial"
    await db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        Payment(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner.id,
            package_id=package.id,
            amount=Decimal("100.00"),
            currency="RUB",
            paid_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get("/api/v1/finance/dashboard", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["total_outstanding"])) == Decimal("0")
    assert body["unpaid_learners_count"] == 0


@pytest.mark.asyncio
async def test_learner_finance_uses_actual_outstanding_even_when_status_is_stale(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, status="active")
    package.price = Decimal("100.00")
    package.payment_status = "paid"
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)

    assert response.status_code == 200
    assert Decimal(str(response.json()["outstanding_balance"])) == Decimal("100")


@pytest.mark.asyncio
async def test_debtors_use_imputed_price_for_legacy_package_without_price(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    learner.lesson_rate = Decimal("2500.00")
    package = await factories.create_package(
        db_session,
        learner=learner,
        status="active",
        total_lessons=8,
    )
    package.price = None
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    finance_response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)
    assert finance_response.status_code == 200
    assert Decimal(str(finance_response.json()["outstanding_balance"])) == Decimal("20000.00")

    dashboard = await client.get("/api/v1/finance/dashboard", headers=headers)
    assert dashboard.status_code == 200
    dashboard_body = dashboard.json()
    assert Decimal(str(dashboard_body["total_outstanding"])) == Decimal("20000.00")
    assert dashboard_body["unpaid_learners_count"] == 1

    debtors = await client.get("/api/v1/finance/debtors?limit=10&offset=0", headers=headers)
    assert debtors.status_code == 200
    body = debtors.json()
    assert body["total"] == 1
    assert body["items"][0]["learner_id"] == learner.id
    assert Decimal(str(body["items"][0]["outstanding_balance"])) == Decimal("20000.00")


@pytest.mark.asyncio
async def test_unassigned_payment_reduces_learner_outstanding_balance(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    first = await factories.create_package(
        db_session,
        learner=learner,
        package_type="one_off",
        status="active",
    )
    second = await factories.create_package(
        db_session,
        learner=learner,
        package_type="one_off",
        status="active",
    )
    first.price = Decimal("2500.00")
    second.price = Decimal("2500.00")
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(
        Payment(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner.id,
            package_id=None,
            amount=Decimal("5000.00"),
            currency="RUB",
            paid_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    finance_response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)
    assert finance_response.status_code == 200
    body = finance_response.json()
    assert Decimal(str(body["total_paid"])) == Decimal("5000.00")
    assert Decimal(str(body["outstanding_balance"])) == Decimal("0")

    dashboard = await client.get("/api/v1/finance/dashboard", headers=headers)
    assert dashboard.status_code == 200
    dashboard_body = dashboard.json()
    assert Decimal(str(dashboard_body["total_outstanding"])) == Decimal("0")
    assert dashboard_body["unpaid_learners_count"] == 0

    debtors = await client.get("/api/v1/finance/debtors?limit=10&offset=0", headers=headers)
    assert debtors.status_code == 200
    assert debtors.json()["total"] == 0


@pytest.mark.asyncio
async def test_debtors_endpoint_matches_dashboard_count(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner_1 = await factories.create_learner(db_session, display_name="A")
    learner_2 = await factories.create_learner(db_session, display_name="B")
    active_1 = await factories.create_package(db_session, learner=learner_1, status="active")
    active_2 = await factories.create_package(db_session, learner=learner_2, status="active")
    draft = await factories.create_package(db_session, learner=learner_2, status="draft")
    active_1.price = Decimal("100.00")
    active_2.price = Decimal("50.00")
    draft.price = Decimal("999.00")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    dashboard = await client.get("/api/v1/finance/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["unpaid_learners_count"] == 2

    debtors = await client.get("/api/v1/finance/debtors?limit=10&offset=0", headers=headers)
    assert debtors.status_code == 200
    body = debtors.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
