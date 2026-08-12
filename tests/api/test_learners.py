from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests import factories
from tests.api.utils import get_auth_headers
from database import crud
from api.dependencies import CurrentTenant
from api.routes import learners as learner_routes


@pytest.mark.asyncio
async def test_list_learners_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/learners")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_learners(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, display_name="Student A", chat_id=555)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/learners", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["display_name"] == learner.display_name
    assert data["items"][0]["chat_id"] == learner.bot_user.chat_id
    assert data["items"][0]["is_archived"] is False


@pytest.mark.asyncio
async def test_list_learners_defaults_to_active_and_can_show_archive(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    active = await factories.create_learner(db_session, display_name="Active Student")
    archived = await factories.create_learner(
        db_session,
        display_name="Archived Student",
        archived_at=datetime.now(timezone.utc),
        notifications_enabled=False,
    )
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    active_response = await client.get("/api/v1/learners", headers=headers)
    archived_response = await client.get("/api/v1/learners", params={"status": "archived"}, headers=headers)
    all_response = await client.get("/api/v1/learners", params={"status": "all"}, headers=headers)

    assert active_response.status_code == 200
    assert [item["id"] for item in active_response.json()["items"]] == [active.id]
    assert archived_response.status_code == 200
    assert [item["id"] for item in archived_response.json()["items"]] == [archived.id]
    assert archived_response.json()["items"][0]["is_archived"] is True
    assert all_response.status_code == 200
    assert {item["id"] for item in all_response.json()["items"]} == {active.id, archived.id}


@pytest.mark.asyncio
async def test_viewer_cannot_list_or_read_learners(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, display_name="Hidden Student")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant, role="viewer")

    list_response = await client.get("/api/v1/learners", headers=headers)
    detail_response = await client.get(f"/api/v1/learners/{learner.id}", headers=headers)
    finance_response = await client.get(f"/api/v1/learners/{learner.id}/finance", headers=headers)

    assert list_response.status_code == 403
    assert detail_response.status_code == 403
    assert finance_response.status_code == 403


@pytest.mark.asyncio
async def test_create_learner_from_chat_id(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    payload = {
        "chat_id": 12345,
        "display_name": "New Learner",
        "notes": "Created via API",
        "notifications_enabled": True,
    }
    response = await client.post("/api/v1/learners", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "New Learner"
    assert body["notifications_enabled"] is True
    assert body["chat_id"] == 12345

    learner = await crud.get_learner(db_session, current_tenant, body["id"])
    assert learner is not None
    assert learner.notifications_enabled is True


@pytest.mark.asyncio
async def test_create_learner_without_chat_id(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    payload = {
        "display_name": "Unlinked Learner",
        "notes": "Invite later",
        "notifications_enabled": True,
    }

    response = await client.post("/api/v1/learners", json=payload, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Unlinked Learner"
    assert body["chat_id"] is None
    assert body["notifications_enabled"] is False

    learner = await crud.get_learner(db_session, current_tenant, body["id"])
    assert learner is not None
    assert learner.bot_user_id is None


@pytest.mark.asyncio
async def test_create_personal_invite_for_unlinked_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    monkeypatch,
):
    refresh_reasons = []

    async def fake_refresh(session, tenant, refreshed_learner, *, reason):
        refresh_reasons.append((refreshed_learner.id, reason))

    monkeypatch.setattr(
        learner_routes.learner_service,
        "refresh_learner_notification_schedules",
        fake_refresh,
    )
    learner = await factories.create_learner(db_session, display_name="Linked")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)
    unlink_response = await client.post(
        f"/api/v1/learners/{learner.id}/unlink-account",
        json={"reason": "prepare personal invite"},
        headers=headers,
    )
    assert unlink_response.status_code == 200
    assert refresh_reasons == [(learner.id, "learner_account_unlinked")]

    response = await client.post(f"/api/v1/learners/{learner.id}/invite", headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["learner_id"] == learner.id
    assert body["learner_name"] == "Linked"
    assert body["is_valid"] is True


@pytest.mark.asyncio
async def test_create_personal_invite_rejects_linked_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, display_name="Already Linked")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.post(f"/api/v1/learners/{learner.id}/invite", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Learner is already linked to a Telegram account"


@pytest.mark.asyncio
async def test_update_learner_notifications(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, notifications_enabled=True)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.patch(
        f"/api/v1/learners/{learner.id}/notifications",
        json={"notifications_enabled": False},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notifications_enabled"] is False

    refreshed = await crud.get_learner(db_session, current_tenant, learner.id)
    assert refreshed is not None
    assert refreshed.notifications_enabled is False


@pytest.mark.asyncio
async def test_update_learner_notifications_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.patch(
        "/api/v1/learners/999/notifications",
        json={"notifications_enabled": False},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archive_learner_disables_notifications_and_restore_keeps_them_disabled(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, notifications_enabled=True)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    archive_response = await client.post(f"/api/v1/learners/{learner.id}/archive", headers=headers)

    assert archive_response.status_code == 200
    archive_body = archive_response.json()
    assert archive_body["is_archived"] is True
    assert archive_body["archived_at"] is not None
    assert archive_body["notifications_enabled"] is False

    enable_response = await client.patch(
        f"/api/v1/learners/{learner.id}/notifications",
        json={"notifications_enabled": True},
        headers=headers,
    )
    assert enable_response.status_code == 409

    restore_response = await client.post(f"/api/v1/learners/{learner.id}/restore", headers=headers)

    assert restore_response.status_code == 200
    restore_body = restore_response.json()
    assert restore_body["is_archived"] is False
    assert restore_body["archived_at"] is None
    assert restore_body["notifications_enabled"] is False
