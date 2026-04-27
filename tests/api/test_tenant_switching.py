"""
Tests for tenant switching functionality.
Critical security tests for SaaS multi-tenancy.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from api.security import create_access_token, decode_token, TokenType
from config import config
from database import crud
from database.models import User, Tenant
from tests import factories


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
async def test_switch_tenant_super_admin_success(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_2: Tenant
):
    """Test that super-admin can successfully switch to another tenant."""
    headers = await get_auth_headers(super_admin_user)
    
    payload = {"tenant_id": tenant_2.id}
    response = await client.post("/api/v1/auth/switch-tenant", json=payload, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify new token contains the target tenant_id
    new_token = data["access_token"]
    token_payload = decode_token(new_token, TokenType.ACCESS)
    assert token_payload["tenant_id"] == tenant_2.id
    assert token_payload["role"] == "admin"


@pytest.mark.asyncio
async def test_switch_tenant_to_global_context(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Test that super-admin can switch to global context (tenant_id = null)."""
    headers = await get_auth_headers(super_admin_user)
    
    payload = {"tenant_id": None}
    response = await client.post("/api/v1/auth/switch-tenant", json=payload, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify new token has null tenant_id
    new_token = data["access_token"]
    token_payload = decode_token(new_token, TokenType.ACCESS)
    assert token_payload["tenant_id"] is None
    assert token_payload["role"] == "admin"


@pytest.mark.asyncio
async def test_switch_tenant_to_global_context_for_tenant_bound_platform_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    monkeypatch,
):
    """Platform admins attached to a tenant can still switch into global mode."""
    telegram_id = 987654321
    monkeypatch.setattr(config, "ADMINS", [*config.ADMINS, telegram_id])
    tenant_bound_admin = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1),
        telegram_id=telegram_id,
        display_name="Tenant Bound Platform Admin",
        role="admin",
        tenant_id=tenant_1.id,
        username="tenant_bound_platform_admin",
    )
    await db_session.commit()

    headers = await get_auth_headers(tenant_bound_admin)
    response = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": None},
        headers=headers,
    )

    assert response.status_code == 200
    token_payload = decode_token(response.json()["access_token"], TokenType.ACCESS)
    assert token_payload["tenant_id"] is None
    assert token_payload["role"] == "admin"


@pytest.mark.asyncio
async def test_switch_tenant_regular_user_forbidden(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, tenant_2: Tenant
):
    """Test that regular users cannot switch tenants."""
    headers = await get_auth_headers(user_tenant_1)
    
    payload = {"tenant_id": tenant_2.id}
    response = await client.post("/api/v1/auth/switch-tenant", json=payload, headers=headers)
    
    assert response.status_code == 403
    assert "Only super-admins" in response.json()["detail"]


@pytest.mark.asyncio
async def test_switch_tenant_nonexistent_tenant(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Test switching to non-existent tenant returns 404."""
    headers = await get_auth_headers(super_admin_user)
    
    payload = {"tenant_id": 99999}  # Non-existent tenant
    response = await client.post("/api/v1/auth/switch-tenant", json=payload, headers=headers)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_switch_tenant_inactive_tenant(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User
):
    """Test switching to inactive tenant returns 403."""
    # Create inactive tenant
    inactive_tenant = Tenant(id=99, name="Inactive Tenant", slug="inactive", is_active=False)
    db_session.add(inactive_tenant)
    await db_session.commit()
    
    headers = await get_auth_headers(super_admin_user)
    
    payload = {"tenant_id": inactive_tenant.id}
    response = await client.post("/api/v1/auth/switch-tenant", json=payload, headers=headers)
    
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"]


@pytest.mark.asyncio
async def test_switched_context_affects_data_access(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_1: Tenant, tenant_2: Tenant
):
    """Test that switched tenant context actually affects data access."""
    # Create learners in different tenants
    learner_t1 = await factories.create_learner(db_session, display_name="T1 Learner", tenant_id=tenant_1.id)
    learner_t2 = await factories.create_learner(db_session, display_name="T2 Learner", tenant_id=tenant_2.id)
    await db_session.commit()
    
    # Switch to tenant 1 context
    headers = await get_auth_headers(super_admin_user)
    switch_payload = {"tenant_id": tenant_1.id}
    switch_response = await client.post("/api/v1/auth/switch-tenant", json=switch_payload, headers=headers)
    assert switch_response.status_code == 200
    
    # Use new token to access learners
    new_token = switch_response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    
    learners_response = await client.get("/api/v1/learners", headers=new_headers)
    assert learners_response.status_code == 200
    
    learners_data = learners_response.json()
    # Should only see tenant 1 learners when in tenant 1 context
    assert len(learners_data["items"]) == 1
    assert learners_data["items"][0]["display_name"] == "T1 Learner"


@pytest.mark.asyncio
async def test_global_context_sees_all_data(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_1: Tenant, tenant_2: Tenant
):
    """Test that global context (tenant_id=null) sees all data."""
    # Create learners in different tenants
    await factories.create_learner(db_session, display_name="T1 Learner", tenant_id=tenant_1.id)
    await factories.create_learner(db_session, display_name="T2 Learner", tenant_id=tenant_2.id)
    await db_session.commit()
    
    # Switch to global context
    headers = await get_auth_headers(super_admin_user)
    switch_payload = {"tenant_id": None}
    switch_response = await client.post("/api/v1/auth/switch-tenant", json=switch_payload, headers=headers)
    assert switch_response.status_code == 200
    
    # Use new token to access learners
    new_token = switch_response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    
    learners_response = await client.get("/api/v1/learners", headers=new_headers)
    assert learners_response.status_code == 200
    
    learners_data = learners_response.json()
    # Should see all learners in global context
    assert len(learners_data["items"]) == 2
