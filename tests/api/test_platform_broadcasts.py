from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_access_token
from database.models import BroadcastCampaign, BroadcastRecipient, User
from services import broadcast_service
from tests import factories


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
async def test_broadcast_preview_counts_non_bot_users(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=101, first_name="Anna")
    await factories.create_bot_user(db_session, chat_id=102, first_name="Bot", is_bot=True)
    await factories.create_bot_user(db_session, chat_id=103, username="student")
    await db_session.commit()

    response = await client.post(
        "/api/v1/platform/broadcasts/preview",
        json={"audience": "all_bot_users", "sample_limit": 10},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert [item["chat_id"] for item in data["sample"]] == [101, 103]


@pytest.mark.asyncio
async def test_broadcast_preview_can_target_platform_admins_only(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=super_admin_user.telegram_id, first_name="Owner")
    await factories.create_bot_user(db_session, chat_id=111_222, first_name="Regular")
    await db_session.commit()

    response = await client.post(
        "/api/v1/platform/broadcasts/preview",
        json={"audience": "platform_admins", "sample_limit": 10},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["sample"][0]["chat_id"] == super_admin_user.telegram_id


@pytest.mark.asyncio
async def test_broadcast_preview_can_target_teachers_only(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    teacher = await factories.create_user(db_session, telegram_id=501_001, role="teacher")
    await factories.create_user(db_session, telegram_id=501_002, role="viewer")
    await factories.create_user(db_session, telegram_id=501_003, role="teacher")
    await factories.create_bot_user(db_session, chat_id=teacher.telegram_id, first_name="Teacher")
    await factories.create_bot_user(db_session, chat_id=501_002, first_name="Viewer")
    await factories.create_bot_user(db_session, chat_id=501_004, first_name="Unlinked")
    await db_session.commit()

    response = await client.post(
        "/api/v1/platform/broadcasts/preview",
        json={"audience": "teachers", "sample_limit": 10},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [item["chat_id"] for item in data["sample"]] == [teacher.telegram_id]


@pytest.mark.asyncio
async def test_broadcast_create_can_target_selected_bot_users(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    selected = await factories.create_bot_user(db_session, chat_id=901, first_name="Selected")
    await factories.create_bot_user(db_session, chat_id=902, first_name="Skipped")
    await db_session.commit()

    response = await client.post(
        "/api/v1/platform/broadcasts",
        json={
            "title": "Selected",
            "message_text": "Only one",
            "audience": "selected_bot_users",
            "bot_user_ids": [selected.id],
        },
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["audience"] == "selected_bot_users"
    assert data["recipient_count"] == 1
    recipients_result = await db_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.campaign_id == data["id"])
    )
    assert [recipient.chat_id for recipient in recipients_result.scalars().all()] == [901]


@pytest.mark.asyncio
async def test_selected_broadcast_requires_recipient_ids(
    client: AsyncClient,
    super_admin_user: User,
):
    response = await client.post(
        "/api/v1/platform/broadcasts/preview",
        json={"audience": "selected_bot_users", "bot_user_ids": []},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_broadcast_audience_users_marks_platform_admins(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=super_admin_user.telegram_id, first_name="Owner")
    await factories.create_bot_user(db_session, chat_id=777, username="regular")
    await db_session.commit()

    response = await client.get(
        "/api/v1/platform/broadcasts/audience/users",
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    owner = next(item for item in items if item["chat_id"] == super_admin_user.telegram_id)
    regular = next(item for item in items if item["chat_id"] == 777)
    assert owner["is_platform_admin"] is True
    assert regular["is_platform_admin"] is False


@pytest.mark.asyncio
async def test_broadcast_create_snapshots_recipients_without_sending(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=201, first_name="One")
    await factories.create_bot_user(db_session, chat_id=202, first_name="Two")
    await db_session.commit()

    response = await client.post(
        "/api/v1/platform/broadcasts",
        json={
            "title": "Bot update",
            "message_text": "Новый бот готов.",
            "audience": "all_bot_users",
            "rate_limit_per_second": 5,
        },
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["recipient_count"] == 2
    assert data["sent_count"] == 0

    recipients_result = await db_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.campaign_id == data["id"])
    )
    recipients = list(recipients_result.scalars().all())
    assert [recipient.chat_id for recipient in recipients] == [201, 202]
    assert {recipient.status for recipient in recipients} == {"pending"}


@pytest.mark.asyncio
async def test_broadcast_send_requires_confirmation(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=301)
    await db_session.commit()
    create_response = await client.post(
        "/api/v1/platform/broadcasts",
        json={"title": "Draft", "message_text": "Text", "audience": "all_bot_users"},
        headers=auth_headers(super_admin_user),
    )

    response = await client.post(
        f"/api/v1/platform/broadcasts/{create_response.json()['id']}/send",
        json={"confirmation_text": "send"},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 400
    campaign = await db_session.get(BroadcastCampaign, create_response.json()["id"])
    assert campaign.status == "draft"


@pytest.mark.asyncio
async def test_broadcast_send_queues_task_after_explicit_confirmation(
    client: AsyncClient,
    db_session: AsyncSession,
    super_admin_user: User,
    monkeypatch,
):
    queued_campaign_ids: list[int] = []

    class FakeTask:
        id = "task-123"

    def fake_delay(*, campaign_id: int):
        queued_campaign_ids.append(campaign_id)
        return FakeTask()

    monkeypatch.setattr("api.routes.platform.send_broadcast_campaign_task.delay", fake_delay)

    await factories.create_bot_user(db_session, chat_id=401)
    await db_session.commit()
    create_response = await client.post(
        "/api/v1/platform/broadcasts",
        json={"title": "Draft", "message_text": "Text", "audience": "all_bot_users"},
        headers=auth_headers(super_admin_user),
    )
    campaign_id = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/platform/broadcasts/{campaign_id}/send",
        json={"confirmation_text": "SEND"},
        headers=auth_headers(super_admin_user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["last_task_id"] == "task-123"
    assert queued_campaign_ids == [campaign_id]


@pytest.mark.asyncio
async def test_broadcasts_are_platform_admin_only(
    client: AsyncClient,
    teacher_user: User,
):
    response = await client.post(
        "/api/v1/platform/broadcasts/preview",
        json={"audience": "all_bot_users"},
        headers=auth_headers(teacher_user),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_broadcast_delivery_records_success_and_failure(
    db_session: AsyncSession,
    super_admin_user: User,
):
    await factories.create_bot_user(db_session, chat_id=501)
    await factories.create_bot_user(db_session, chat_id=502)
    await db_session.commit()
    campaign = await broadcast_service.create_broadcast_campaign(
        db_session,
        title="Delivery",
        message_text="Hello",
        created_by_user_id=super_admin_user.id,
    )
    await broadcast_service.queue_broadcast_campaign(
        db_session,
        campaign_id=campaign.id,
        confirmation_text="SEND",
    )
    await db_session.commit()

    async def fake_send(chat_id: int, message_text: str) -> str:
        if chat_id == 502:
            raise RuntimeError("blocked by user")
        return f"message-{chat_id}"

    async def no_sleep(_: float) -> None:
        return None

    result = await broadcast_service.deliver_broadcast_campaign(
        db_session,
        campaign_id=campaign.id,
        send_message=fake_send,
        sleep=no_sleep,
    )

    assert result == {"status": "completed", "sent": 1, "failed": 1}
    recipients_result = await db_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.campaign_id == campaign.id)
    )
    recipients = {recipient.chat_id: recipient for recipient in recipients_result.scalars().all()}
    assert recipients[501].status == "sent"
    assert recipients[501].provider_message_id == "message-501"
    assert recipients[502].status == "failed"
    assert recipients[502].error_message == "blocked by user"
