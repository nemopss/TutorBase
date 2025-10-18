from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_list_users_requires_admin(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    non_admin_headers, _ = await get_auth_headers(db_session, current_tenant, role="viewer")
    response = await client.get("/api/v1/users", headers=non_admin_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant, role="admin")
    await crud.create_user(
        db_session,
        current_tenant,
        telegram_id=42,
        username="second",
        display_name="Second User",
        role="viewer",
    )
    await db_session.commit()

    response = await client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert any(user["username"] == "second" for user in data["users"])


@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant, role="admin")
    user = await crud.create_user(
        db_session,
        current_tenant,
        telegram_id=100,
        username="promote_me",
        display_name="Promote Me",
        role="viewer",
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/users/{user.id}/role",
        json={"role": "teacher"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "teacher"

    refreshed = await crud.get_user(db_session, user.id)
    assert refreshed.role == "teacher"


@pytest.mark.asyncio
async def test_update_user_role_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant, role="admin")
    response = await client.patch(
        "/api/v1/users/999/role",
        json={"role": "teacher"},
        headers=headers,
    )
    assert response.status_code == 404
