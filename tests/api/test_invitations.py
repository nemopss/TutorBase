"""Tests for invite token management endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Tenant, User
from tests import factories


@pytest.mark.asyncio
async def test_create_invite_token_success(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test successful invite token creation by teacher."""
    response = await client.post(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        json={"expires_in_days": 30},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "token" in data
    assert "expires_at" in data
    assert "created_at" in data
    assert data["is_used"] is False
    assert data["is_expired"] is False
    assert data["is_valid"] is True
    assert len(data["token"]) > 20  # Secure token


@pytest.mark.asyncio
async def test_create_invite_token_custom_expiry(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test invite token creation with custom expiry."""
    response = await client.post(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        json={"expires_in_days": 7, "note": "Test invite"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["note"] == "Test invite"


@pytest.mark.asyncio
async def test_create_invite_token_forbidden_for_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    viewer_user: User,
    viewer_token: str,
):
    """Test that viewers (students) cannot create invite tokens."""
    response = await client.post(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        json={"expires_in_days": 30},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    
    assert response.status_code == 403
    assert "Only teachers and admins" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_invite_token_wrong_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    tenant_2: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test that teachers cannot create invites for other tenants."""
    # teacher_user belongs to tenant_1, trying to create for tenant_2
    response = await client.post(
        f"/api/v1/tenants/{tenant_2.id}/invitations",
        json={"expires_in_days": 30},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 403
    assert "your own tenant" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_invite_tokens_success(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test listing invite tokens for a tenant."""
    # Create some invite tokens first
    await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        created_by_user_id=teacher_user.id,
    )
    await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        created_by_user_id=teacher_user.id,
    )
    await db_session.commit()
    
    response = await client.get(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "tokens" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["tokens"]) >= 2
    
    # Check token structure
    token = data["tokens"][0]
    assert "token" in token
    assert "expires_at" in token
    assert "is_valid" in token


@pytest.mark.asyncio
async def test_list_invite_tokens_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test pagination of invite tokens list."""
    # Create multiple tokens
    for _ in range(5):
        await factories.create_invite_token(
            db_session,
            tenant_id=tenant_1.id,
            created_by_user_id=teacher_user.id,
        )
    await db_session.commit()
    
    # Get first page
    response = await client.get(
        f"/api/v1/tenants/{tenant_1.id}/invitations?limit=2&offset=0",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["tokens"]) == 2
    assert data["total"] >= 5


@pytest.mark.asyncio
async def test_list_invite_tokens_forbidden_for_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    viewer_user: User,
    viewer_token: str,
):
    """Test that viewers cannot list invite tokens."""
    response = await client.get(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    
    assert response.status_code == 403
    assert "Only teachers and admins" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_invite_tokens_wrong_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    tenant_2: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test that teachers cannot list invites for other tenants."""
    response = await client.get(
        f"/api/v1/tenants/{tenant_2.id}/invitations",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 403
    assert "your own tenant" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_invite_tokens_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    teacher_user: User,
    teacher_token: str,
):
    """Test listing invite tokens when none exist."""
    response = await client.get(
        f"/api/v1/tenants/{tenant_1.id}/invitations",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["tokens"] == []
