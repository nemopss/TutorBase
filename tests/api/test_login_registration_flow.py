"""Tests for login endpoint with registration flow."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_login_new_user_requires_registration(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that login returns 404 with X-Registration-Required for new users."""
    # Try to login with Telegram init data (DEV_MODE)
    response = await client.post(
        "/api/v1/auth/login",
        json={"init_data": "dev"},
    )
    
    # Should return 404 with registration header
    assert response.status_code == 404
    assert "X-Registration-Required" in response.headers
    assert response.headers["X-Registration-Required"] == "true"
    assert "not registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_existing_user_success(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that login works for existing users."""
    # First register a user
    response = await client.post(
        "/api/v1/auth/register-tutor",
        json={
            "school_name": "Existing School",
            "contact_email": "existing@example.com",
            "email": "existing@example.com",
            "password": "password123",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )
    assert response.status_code == 200
    
    # Now login should work for the same user
    response = await client.post(
        "/api/v1/auth/login",
        json={"init_data": "dev"},
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data


@pytest.mark.asyncio
async def test_full_registration_then_login_flow(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test complete flow: login fails -> register -> login succeeds."""
    
    # Step 1: Try to login (should fail - user doesn't exist)
    response = await client.post(
        "/api/v1/auth/login",
        json={"init_data": "dev"},
    )
    assert response.status_code == 404
    assert response.headers.get("X-Registration-Required") == "true"
    
    # Step 2: Register as tutor
    response = await client.post(
        "/api/v1/auth/register-tutor",
        json={
            "school_name": "Test School",
            "contact_email": "test@example.com",
            "email": "test@example.com",
            "password": "password123",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )
    assert response.status_code == 200
    registration_data = response.json()
    assert "access_token" in registration_data
    
    # Step 3: Now login should work
    response = await client.post(
        "/api/v1/auth/login",
        json={"init_data": "dev"},
    )
    assert response.status_code == 200
    login_data = response.json()
    assert "access_token" in login_data
    assert login_data["user"]["role"] == "teacher"
