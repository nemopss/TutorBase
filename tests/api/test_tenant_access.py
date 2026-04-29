from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_access_token
from database.models import Tenant, TenantAccess, TenantAccessEvent, User
from services.tenant_access_service import (
    ACCESS_STATUS_ACTIVE,
    ACCESS_STATUS_EXPIRED,
    ACCESS_STATUS_GRACE,
    ACCESS_STATUS_LIFETIME,
    ACCESS_STATUS_SUSPENDED,
    ACCESS_STATUS_TRIAL,
    utc_now,
)
from tests import factories


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "telegram_id": user.telegram_id,
            "tenant_id": user.tenant_id,
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def put_tenant_in_grace(db_session: AsyncSession, tenant: Tenant) -> None:
    now = utc_now()
    db_session.add(
        TenantAccess(
            tenant_id=tenant.id,
            status=ACCESS_STATUS_ACTIVE,
            access_until=now - timedelta(days=1),
            grace_until=now + timedelta(days=2),
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_platform_tenant_list_includes_access_state(
    client: AsyncClient,
    super_admin_user: User,
    tenant_1: Tenant,
):
    response = await client.get("/api/v1/platform/tenants", headers=auth_headers(super_admin_user))

    assert response.status_code == 200
    data = response.json()
    tenant = next(item for item in data["items"] if item["id"] == tenant_1.id)
    assert tenant["access"]["status"] == ACCESS_STATUS_LIFETIME
    assert tenant["access"]["mode"] == "full"


@pytest.mark.asyncio
async def test_platform_tenant_detail_exposes_access_state(
    client: AsyncClient,
    super_admin_user: User,
    tenant_1: Tenant,
):
    response = await client.get(
        f"/api/v1/platform/tenants/{tenant_1.id}",
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tenant_1.id
    assert data["access"]["status"] == ACCESS_STATUS_LIFETIME
    assert data["access"]["mode"] == "full"


@pytest.mark.asyncio
async def test_expired_tenant_blocks_regular_tutor_requests(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher_user: User,
    tenant_1: Tenant,
):
    now = utc_now()
    db_session.add(
        TenantAccess(
            tenant_id=tenant_1.id,
            status=ACCESS_STATUS_ACTIVE,
            access_until=now - timedelta(days=2),
            grace_until=now - timedelta(days=1),
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/learners", headers=auth_headers(teacher_user))

    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "TENANT_ACCESS_EXPIRED"

    access_response = await client.get("/api/v1/tenant-access/current", headers=auth_headers(teacher_user))
    assert access_response.status_code == 200
    assert access_response.json()["status"] == "expired"
    assert access_response.json()["mode"] == "blocked"
    assert access_response.json()["bypass_access_restrictions"] is False


@pytest.mark.asyncio
async def test_suspended_tenant_blocks_regular_tutor_requests(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher_user: User,
    tenant_1: Tenant,
):
    now = utc_now()
    db_session.add(
        TenantAccess(
            tenant_id=tenant_1.id,
            status=ACCESS_STATUS_SUSPENDED,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/learners", headers=auth_headers(teacher_user))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "TENANT_ACCESS_SUSPENDED"


@pytest.mark.asyncio
async def test_platform_admin_can_debug_expired_tenant_context(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
    tenant_1: Tenant,
):
    now = utc_now()
    db_session.add(
        TenantAccess(
            tenant_id=tenant_1.id,
            status=ACCESS_STATUS_ACTIVE,
            access_until=now - timedelta(days=2),
            grace_until=now - timedelta(days=1),
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.commit()

    switch_response = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_1.id},
        headers=auth_headers(super_admin_user),
    )
    assert switch_response.status_code == 200
    switched_headers = {"Authorization": f"Bearer {switch_response.json()['access_token']}"}

    response = await client.get("/api/v1/learners", headers=switched_headers)

    assert response.status_code == 200

    access_response = await client.get("/api/v1/tenant-access/current", headers=switched_headers)
    assert access_response.status_code == 200
    assert access_response.json()["status"] == "expired"
    assert access_response.json()["mode"] == "blocked"
    assert access_response.json()["bypass_access_restrictions"] is True


@pytest.mark.asyncio
async def test_platform_access_actions_update_state_and_audit(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
    tenant_1: Tenant,
):
    headers = auth_headers(super_admin_user)

    grant_response = await client.post(
        f"/api/v1/platform/tenants/{tenant_1.id}/access/grant",
        json={"days": 30, "notes": "manual grant"},
        headers=headers,
    )
    assert grant_response.status_code == 200
    assert grant_response.json()["status"] == ACCESS_STATUS_ACTIVE

    suspend_response = await client.post(
        f"/api/v1/platform/tenants/{tenant_1.id}/access/suspend",
        json={"notes": "debug suspend"},
        headers=headers,
    )
    assert suspend_response.status_code == 200
    assert suspend_response.json()["status"] == ACCESS_STATUS_SUSPENDED

    lifetime_response = await client.post(
        f"/api/v1/platform/tenants/{tenant_1.id}/access/lifetime",
        json={"notes": "owner tenant"},
        headers=headers,
    )
    assert lifetime_response.status_code == 200
    assert lifetime_response.json()["status"] == ACCESS_STATUS_LIFETIME
    assert lifetime_response.json()["is_lifetime"] is True

    events_result = await db_session.execute(
        select(TenantAccessEvent).where(TenantAccessEvent.tenant_id == tenant_1.id)
    )
    actions = [event.action for event in events_result.scalars().all()]
    assert actions == ["grant", "suspend", "grant_lifetime"]


@pytest.mark.asyncio
async def test_platform_resume_does_not_extend_access_period(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
    tenant_1: Tenant,
):
    now = utc_now()
    original_access_until = now + timedelta(days=10)
    db_session.add(
        TenantAccess(
            tenant_id=tenant_1.id,
            status=ACCESS_STATUS_SUSPENDED,
            access_until=original_access_until,
            grace_until=original_access_until + timedelta(days=7),
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/platform/tenants/{tenant_1.id}/access/resume",
        json={"notes": "resume support"},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ACCESS_STATUS_ACTIVE
    assert datetime.fromisoformat(body["access_until"].replace("Z", "+00:00")) == original_access_until


@pytest.mark.asyncio
async def test_platform_can_grant_tenant_subscription(
    client: AsyncClient,
    super_admin_user: User,
    tenant_1: Tenant,
):
    now = utc_now()

    response = await client.post(
        f"/api/v1/platform/tenants/{tenant_1.id}/billing/grant",
        json={
            "plan_code": "basic",
            "status": "manual",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "notes": "manual test grant",
        },
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "basic"
    assert body["plan_name"] == "Базовый"
    assert body["active_learners_limit"] == 10
    assert body["notifications_allowed"] is True


@pytest.mark.asyncio
async def test_platform_access_sync_persists_lifecycle_transitions_once(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
    tenant_1: Tenant,
):
    now = utc_now()
    grace_tenant = await factories.create_tenant(db_session)
    active_without_grace_tenant = await factories.create_tenant(db_session)
    lifetime_tenant = await factories.create_tenant(db_session)
    suspended_tenant = await factories.create_tenant(db_session)
    await db_session.flush()

    db_session.add_all(
        [
            TenantAccess(
                tenant_id=tenant_1.id,
                status=ACCESS_STATUS_TRIAL,
                access_until=now - timedelta(days=1),
                grace_until=now + timedelta(days=2),
                created_at=now,
                updated_at=now,
            ),
            TenantAccess(
                tenant_id=grace_tenant.id,
                status=ACCESS_STATUS_GRACE,
                access_until=now - timedelta(days=8),
                grace_until=now - timedelta(days=1),
                created_at=now,
                updated_at=now,
            ),
            TenantAccess(
                tenant_id=active_without_grace_tenant.id,
                status=ACCESS_STATUS_ACTIVE,
                access_until=now - timedelta(days=1),
                grace_until=None,
                created_at=now,
                updated_at=now,
            ),
            TenantAccess(
                tenant_id=lifetime_tenant.id,
                status=ACCESS_STATUS_LIFETIME,
                created_at=now,
                updated_at=now,
            ),
            TenantAccess(
                tenant_id=suspended_tenant.id,
                status=ACCESS_STATUS_SUSPENDED,
                access_until=now - timedelta(days=8),
                grace_until=now - timedelta(days=1),
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    await db_session.commit()
    headers = auth_headers(super_admin_user)

    response = await client.post("/api/v1/platform/access/sync", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"grace_started": 1, "expired": 2, "changed": 3}

    access_rows = {
        access.tenant_id: access
        for access in (
            await db_session.execute(select(TenantAccess))
        ).scalars().all()
    }
    assert access_rows[tenant_1.id].status == ACCESS_STATUS_GRACE
    assert access_rows[grace_tenant.id].status == ACCESS_STATUS_EXPIRED
    assert access_rows[active_without_grace_tenant.id].status == ACCESS_STATUS_EXPIRED
    assert access_rows[lifetime_tenant.id].status == ACCESS_STATUS_LIFETIME
    assert access_rows[suspended_tenant.id].status == ACCESS_STATUS_SUSPENDED

    events = (
        await db_session.execute(
            select(TenantAccessEvent).order_by(TenantAccessEvent.id)
        )
    ).scalars().all()
    assert [event.action for event in events] == ["grace_started", "expired", "expired"]
    assert {event.actor_user_id for event in events} == {super_admin_user.id}

    second_response = await client.post("/api/v1/platform/access/sync", headers=headers)

    assert second_response.status_code == 200
    assert second_response.json() == {"grace_started": 0, "expired": 0, "changed": 0}
    event_count = (
        await db_session.execute(select(TenantAccessEvent))
    ).scalars().all()
    assert len(event_count) == 3


@pytest.mark.asyncio
async def test_grace_mode_allows_existing_lesson_maintenance(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher_user: User,
    tenant_1: Tenant,
):
    learner = await factories.create_learner(db_session, tenant_id=tenant_1.id)
    package = await factories.create_package(db_session, learner=learner, tenant_id=tenant_1.id)
    lesson = await factories.create_lesson(db_session, package=package, tenant_id=tenant_1.id)
    await put_tenant_in_grace(db_session, tenant_1)

    new_time = (utc_now() + timedelta(days=3)).isoformat()
    response = await client.patch(
        f"/api/v1/lessons/{lesson.id}",
        json={"scheduled_at": new_time, "duration_minutes": 90},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 90


@pytest.mark.asyncio
async def test_grace_mode_allows_payment_corrections(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher_user: User,
    tenant_1: Tenant,
):
    learner = await factories.create_learner(db_session, tenant_id=tenant_1.id)
    package = await factories.create_package(db_session, learner=learner, tenant_id=tenant_1.id)
    await put_tenant_in_grace(db_session, tenant_1)

    response = await client.post(
        "/api/v1/payments",
        json={
            "learner_id": learner.id,
            "package_id": package.id,
            "amount": "1500.00",
            "paid_at": utc_now().isoformat(),
            "notes": "grace correction",
        },
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 201
    assert response.json()["package_id"] == package.id


@pytest.mark.asyncio
async def test_grace_mode_blocks_new_business_usage(
    client: AsyncClient,
    db_session: AsyncSession,
    teacher_user: User,
    tenant_1: Tenant,
):
    learner = await factories.create_learner(db_session, tenant_id=tenant_1.id)
    package = await factories.create_package(db_session, learner=learner, tenant_id=tenant_1.id)
    await put_tenant_in_grace(db_session, tenant_1)
    headers = auth_headers(teacher_user)

    create_learner_response = await client.post(
        "/api/v1/learners",
        json={"chat_id": None, "display_name": "New Learner"},
        headers=headers,
    )
    assert create_learner_response.status_code == 403
    assert create_learner_response.json()["detail"]["code"] == "TENANT_ACCESS_FULL_REQUIRED"

    create_package_response = await client.post(
        "/api/v1/packages",
        json={"learner_id": learner.id, "title": "New Package", "status": "draft"},
        headers=headers,
    )
    assert create_package_response.status_code == 403
    assert create_package_response.json()["detail"]["code"] == "TENANT_ACCESS_FULL_REQUIRED"

    create_lesson_response = await client.post(
        f"/api/v1/lessons/packages/{package.id}",
        json={"scheduled_at": (utc_now() + timedelta(days=5)).isoformat()},
        headers=headers,
    )
    assert create_lesson_response.status_code == 403
    assert create_lesson_response.json()["detail"]["code"] == "TENANT_ACCESS_FULL_REQUIRED"

    invite_response = await client.post(
        f"/api/v1/learners/{learner.id}/invite",
        headers=headers,
    )
    assert invite_response.status_code == 403
    assert invite_response.json()["detail"]["code"] == "TENANT_ACCESS_FULL_REQUIRED"
