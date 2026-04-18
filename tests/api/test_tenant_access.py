from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_access_token
from database.models import Tenant, TenantAccess, TenantAccessEvent, User
from services.tenant_access_service import (
    ACCESS_STATUS_ACTIVE,
    ACCESS_STATUS_LIFETIME,
    ACCESS_STATUS_SUSPENDED,
    utc_now,
)


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
