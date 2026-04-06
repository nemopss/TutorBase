from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_access_token
from database.models import User, Tenant


async def get_auth_headers(user: User) -> dict[str, str]:
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
async def test_create_tenant_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Super-admin can create a new tenant."""
    headers = await get_auth_headers(super_admin_user)
    payload = {
        "name": "New Tenant",
        "slug": "new-tenant",
        "contact_email": "contact@new.com",
        "is_active": True,
    }
    response = await client.post("/api/v1/tenants", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Tenant"
    assert data["slug"] == "new-tenant"
    assert data["contact_email"] == "contact@new.com"
    assert data["is_active"] is True

    tenant = await db_session.get(Tenant, data["id"])
    assert tenant is not None
    assert tenant.name == "New Tenant"


@pytest.mark.asyncio
async def test_create_tenant_non_super_admin_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User
):
    """Non-super-admin cannot create a tenant."""
    headers = await get_auth_headers(user_tenant_1)
    payload = {
        "name": "Forbidden Tenant",
        "slug": "forbidden-tenant",
    }
    response = await client.post("/api/v1/tenants", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_tenants_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_2: Tenant
):
    """Super-admin can list all tenants."""
    headers = await get_auth_headers(super_admin_user)
    response = await client.get("/api/v1/tenants", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    slugs = {t["slug"] for t in data["items"]}
    assert "default" in slugs
    assert tenant_2.slug in slugs


@pytest.mark.asyncio
async def test_list_tenants_super_admin_in_switched_context_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_1: Tenant, tenant_2: Tenant
):
    """Super-admin can list tenants after switching into a tenant context."""
    headers = await get_auth_headers(super_admin_user)
    switch_response = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_1.id},
        headers=headers,
    )
    assert switch_response.status_code == 200

    switched_headers = {"Authorization": f"Bearer {switch_response.json()['access_token']}"}
    response = await client.get("/api/v1/tenants", headers=switched_headers)

    assert response.status_code == 200
    slugs = {t["slug"] for t in response.json()["items"]}
    assert tenant_1.slug in slugs
    assert tenant_2.slug in slugs


@pytest.mark.asyncio
async def test_list_tenants_non_super_admin_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User
):
    """Non-super-admin cannot list tenants."""
    headers = await get_auth_headers(user_tenant_1)
    response = await client.get("/api/v1/tenants", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_tenant_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_2: Tenant
):
    """Super-admin can get a specific tenant."""
    headers = await get_auth_headers(super_admin_user)
    response = await client.get(f"/api/v1/tenants/{tenant_2.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tenant_2.id
    assert data["slug"] == tenant_2.slug


@pytest.mark.asyncio
async def test_get_tenant_super_admin_in_switched_context_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_1: Tenant, tenant_2: Tenant
):
    """Super-admin can read tenant details after switching into a tenant context."""
    headers = await get_auth_headers(super_admin_user)
    switch_response = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_1.id},
        headers=headers,
    )
    assert switch_response.status_code == 200

    switched_headers = {"Authorization": f"Bearer {switch_response.json()['access_token']}"}
    response = await client.get(f"/api/v1/tenants/{tenant_2.id}", headers=switched_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tenant_2.id
    assert data["slug"] == tenant_2.slug


@pytest.mark.asyncio
async def test_get_tenant_super_admin_not_found(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Super-admin gets 404 for non-existent tenant."""
    headers = await get_auth_headers(super_admin_user)
    response = await client.get("/api/v1/tenants/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tenant_non_super_admin_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, tenant_2: Tenant
):
    """Non-super-admin cannot get a specific tenant."""
    headers = await get_auth_headers(user_tenant_1)
    response = await client.get(f"/api/v1/tenants/{tenant_2.id}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_tenant_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_2: Tenant
):
    """Super-admin can update a tenant."""
    headers = await get_auth_headers(super_admin_user)
    payload = {"name": "Updated Tenant Name", "is_active": False}
    response = await client.patch(f"/api/v1/tenants/{tenant_2.id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Tenant Name"
    assert data["is_active"] is False

    updated_tenant = await db_session.get(Tenant, tenant_2.id)
    assert updated_tenant.name == "Updated Tenant Name"
    assert updated_tenant.is_active is False


@pytest.mark.asyncio
async def test_update_tenant_super_admin_not_found(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Super-admin gets 404 for non-existent tenant on update."""
    headers = await get_auth_headers(super_admin_user)
    payload = {"name": "Non Existent"}
    response = await client.patch("/api/v1/tenants/999", json=payload, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_tenant_non_super_admin_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, tenant_2: Tenant
):
    """Non-super-admin cannot update a tenant."""
    headers = await get_auth_headers(user_tenant_1)
    payload = {"name": "Forbidden Update"}
    response = await client.patch(f"/api/v1/tenants/{tenant_2.id}", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_tenant_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_2: Tenant
):
    """Super-admin can delete a tenant."""
    headers = await get_auth_headers(super_admin_user)
    response = await client.delete(f"/api/v1/tenants/{tenant_2.id}", headers=headers)
    assert response.status_code == 204

    deleted_tenant = await db_session.get(Tenant, tenant_2.id)
    assert deleted_tenant is None


@pytest.mark.asyncio
async def test_delete_tenant_super_admin_not_found(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Super-admin gets 404 for non-existent tenant on delete."""
    headers = await get_auth_headers(super_admin_user)
    response = await client.delete("/api/v1/tenants/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_tenant_non_super_admin_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, tenant_2: Tenant
):
    """Non-super-admin cannot delete a tenant."""
    headers = await get_auth_headers(user_tenant_1)
    response = await client.delete(f"/api/v1/tenants/{tenant_2.id}", headers=headers)
    assert response.status_code == 403
