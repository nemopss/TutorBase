"""Tests for user registration endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import InviteToken, Learner, Tenant, User
from tests import factories


@pytest.mark.asyncio
async def test_register_tutor_success(client: AsyncClient, db_session: AsyncSession):
    """Test successful tutor registration."""
    registration_data = {
        "school_name": "Test Tutoring School",
        "contact_email": "test@example.com",
        "tutor_name": "John Doe"
    }
    
    # Mock Telegram init data
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-tutor", json=registration_data, headers=headers)
    
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data
    assert "tenant" in data
    assert "message" in data
    
    # Check user data
    user_data = data["user"]
    assert user_data["role"] == "teacher"
    assert user_data["display_name"] == "John Doe"
    
    # Check tenant data
    tenant_data = data["tenant"]
    assert tenant_data["name"] == "Test Tutoring School"
    assert "slug" in tenant_data


@pytest.mark.asyncio
async def test_register_student_success(client: AsyncClient, db_session: AsyncSession, tenant_1: Tenant):
    """Test successful student registration with valid invite."""
    # Create teacher and invite token
    teacher = await factories.create_user(db_session, role="teacher", tenant_id=tenant_1.id)
    await db_session.flush()  # Get teacher.id
    invite_token = await factories.create_invite_token(db_session, tenant_id=tenant_1.id, created_by_user_id=teacher.id)
    await db_session.commit()
    
    registration_data = {
        "invite_token": invite_token.token,
        "student_name": "Jane Student"
    }
    
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-student", json=registration_data, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "access_token" in data
    assert "user" in data
    assert "tenant" in data
    
    # Check user data
    user_data = data["user"]
    assert user_data["role"] == "viewer"
    assert user_data["display_name"] == "Jane Student"


@pytest.mark.asyncio
async def test_register_student_invalid_token(client: AsyncClient, db_session: AsyncSession):
    """Test student registration with invalid invite token."""
    registration_data = {
        "invite_token": "invalid-token-12345",
        "student_name": "Jane Student"
    }
    
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-student", json=registration_data, headers=headers)
    
    assert response.status_code == 404
    assert "Invalid invite code" in response.json()["detail"]
