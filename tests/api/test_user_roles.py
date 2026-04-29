from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from api.security import create_access_token
from database.models import LearnerAccountLink
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_linked_learner_user_cannot_be_promoted_to_teacher(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    user = await factories.create_user(
        db_session,
        telegram_id=learner.bot_user.chat_id,
        role="viewer",
        tenant_id=current_tenant.tenant_id,
    )
    await db_session.flush()
    db_session.add(
        LearnerAccountLink(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner.id,
            bot_user_id=learner.bot_user_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
        )
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.patch(
        f"/api/v1/users/{user.id}/role",
        json={"role": "teacher"},
        headers=headers,
    )

    assert response.status_code == 409
    await db_session.refresh(user)
    assert user.role == "viewer"


@pytest.mark.asyncio
async def test_unlinked_viewer_user_can_be_promoted_to_teacher(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    user = await factories.create_user(
        db_session,
        role="viewer",
        tenant_id=current_tenant.tenant_id,
    )
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.patch(
        f"/api/v1/users/{user.id}/role",
        json={"role": "teacher"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "teacher"
    await db_session.refresh(user)
    assert user.role == "teacher"


@pytest.mark.asyncio
async def test_existing_linked_teacher_user_is_treated_as_viewer(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, tenant_id=current_tenant.tenant_id)
    user = await factories.create_user(
        db_session,
        telegram_id=learner.bot_user.chat_id,
        role="teacher",
        tenant_id=current_tenant.tenant_id,
    )
    await db_session.flush()
    db_session.add(
        LearnerAccountLink(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner.id,
            bot_user_id=learner.bot_user_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
        )
    )
    await db_session.commit()
    token = create_access_token(
        {
            "sub": str(user.id),
            "role": "teacher",
            "telegram_id": user.telegram_id,
            "tenant_id": user.tenant_id,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    forbidden_response = await client.get("/api/v1/users", headers=headers)
    assert forbidden_response.status_code == 403

    me_response = await client.get("/api/v1/users/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "viewer"
    await db_session.refresh(user)
    assert user.role == "viewer"
