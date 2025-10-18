from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_access_token
from database.models import User, Learner, Tenant
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
async def test_list_learners_isolates_by_tenant(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, user_tenant_2: User
):
    """Tests that GET /learners only returns learners for the user's tenant."""
    # Create learners for both tenants
    learner1 = await factories.create_learner(db_session, display_name="Learner T1", tenant_id=user_tenant_1.tenant_id)
    learner2 = await factories.create_learner(db_session, display_name="Learner T2", tenant_id=user_tenant_2.tenant_id)
    await db_session.commit()

    # --- Test as user from tenant 1 ---
    headers_t1 = await get_auth_headers(user_tenant_1)
    response_t1 = await client.get("/api/v1/learners", headers=headers_t1)
    assert response_t1.status_code == 200
    data_t1 = response_t1.json()
    assert len(data_t1["items"]) == 1
    assert data_t1["items"][0]["display_name"] == learner1.display_name

    # --- Test as user from tenant 2 ---
    headers_t2 = await get_auth_headers(user_tenant_2)
    response_t2 = await client.get("/api/v1/learners", headers=headers_t2)
    assert response_t2.status_code == 200
    data_t2 = response_t2.json()
    assert len(data_t2["items"]) == 1
    assert data_t2["items"][0]["display_name"] == learner2.display_name


@pytest.mark.asyncio
async def test_list_learners_super_admin_sees_all(
    client: AsyncClient, db_session: AsyncSession, super_admin_user: User, tenant_1, tenant_2
):
    """Tests that a super_admin can see learners from all tenants."""
    await factories.create_learner(db_session, display_name="Learner T1", tenant_id=tenant_1.id)
    await factories.create_learner(db_session, display_name="Learner T2", tenant_id=tenant_2.id)
    await db_session.commit()

    headers = await get_auth_headers(super_admin_user)
    response = await client.get("/api/v1/learners", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_learner_isolates_by_tenant(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, user_tenant_2: User
):
    """Tests that a user cannot GET a learner from another tenant."""
    learner2 = await factories.create_learner(db_session, display_name="Learner T2", tenant_id=user_tenant_2.tenant_id)
    await db_session.commit()

    # User from tenant 1 tries to get learner from tenant 2
    headers_t1 = await get_auth_headers(user_tenant_1)
    response = await client.get(f"/api/v1/learners/{learner2.id}", headers=headers_t1)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_learner_assigns_correct_tenant(
    client: AsyncClient, db_session: AsyncSession, user_tenant_2: User
):
    """Tests that a new learner is created in the user's tenant."""
    headers_t2 = await get_auth_headers(user_tenant_2)
    payload = {
        "chat_id": 98765,
        "display_name": "New Learner T2",
    }
    response = await client.post("/api/v1/learners", json=payload, headers=headers_t2)
    assert response.status_code == 201
    data = response.json()
    
    # Verify in DB
    new_learner = await db_session.get(Learner, data["id"])
    assert new_learner is not None
    assert new_learner.tenant_id == user_tenant_2.tenant_id


@pytest.mark.asyncio
async def test_jwt_tenant_mismatch_security(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, user_tenant_2: User
):
    """
    Critical security test: Ensure users cannot use JWT tokens with different tenant_id
    than their actual tenant_id to access other tenant's data.
    """
    # Create a malicious token with user_tenant_1's credentials but user_tenant_2's tenant_id
    malicious_token = create_access_token(
        {
            "sub": str(user_tenant_1.id),
            "role": user_tenant_1.role,
            "telegram_id": user_tenant_1.telegram_id,
            "tenant_id": user_tenant_2.tenant_id,  # Wrong tenant_id!
        }
    )
    
    malicious_headers = {"Authorization": f"Bearer {malicious_token}"}
    
    # This should fail with 403 due to tenant mismatch
    response = await client.get("/api/v1/learners", headers=malicious_headers)
    assert response.status_code == 403
    assert "tenant mismatch" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_inactive_tenant_access_blocked(
    client: AsyncClient, db_session: AsyncSession, user_tenant_1: User, tenant_1: Tenant
):
    """Test that users from inactive tenants cannot access the API."""
    # Deactivate the tenant
    tenant_1.is_active = False
    db_session.add(tenant_1)
    await db_session.commit()
    
    headers = await get_auth_headers(user_tenant_1)
    response = await client.get("/api/v1/learners", headers=headers)
    
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()