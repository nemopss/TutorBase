from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import BotUser, BroadcastCampaign, BroadcastRecipient
from services.exceptions import NotFoundError, ValidationError


BROADCAST_AUDIENCE_ALL_BOT_USERS = "all_bot_users"
BROADCAST_AUDIENCE_PLATFORM_ADMINS = "platform_admins"
BROADCAST_AUDIENCE_SELECTED_BOT_USERS = "selected_bot_users"
BROADCAST_STATUS_DRAFT = "draft"
BROADCAST_STATUS_QUEUED = "queued"
BROADCAST_STATUS_SENDING = "sending"
BROADCAST_STATUS_COMPLETED = "completed"
BROADCAST_STATUS_FAILED = "failed"
BROADCAST_STATUS_CANCELLED = "cancelled"

RECIPIENT_STATUS_PENDING = "pending"
RECIPIENT_STATUS_SENT = "sent"
RECIPIENT_STATUS_FAILED = "failed"

CONFIRMATION_TEXT = "SEND"

SendMessage = Callable[[int, str], Awaitable[str | None]]
Sleep = Callable[[float], Awaitable[None]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BroadcastRecipientPreview:
    bot_user_id: int
    chat_id: int
    display_name: str | None
    username: str | None


@dataclass(frozen=True)
class BroadcastPreview:
    audience: str
    total: int
    sample: list[BroadcastRecipientPreview]


@dataclass(frozen=True)
class BroadcastAudienceUser:
    bot_user_id: int
    chat_id: int
    display_name: str | None
    username: str | None
    is_platform_admin: bool


async def preview_broadcast_recipients(
    session: AsyncSession,
    *,
    audience: str = BROADCAST_AUDIENCE_ALL_BOT_USERS,
    bot_user_ids: list[int] | None = None,
    sample_limit: int = 20,
) -> BroadcastPreview:
    recipient_query = _recipient_query(audience=audience, bot_user_ids=bot_user_ids)
    total_result = await session.execute(select(func.count()).select_from(recipient_query.subquery()))
    sample_result = await session.execute(recipient_query.limit(sample_limit))
    return BroadcastPreview(
        audience=audience,
        total=total_result.scalar_one(),
        sample=[
            BroadcastRecipientPreview(
                bot_user_id=row.id,
                chat_id=row.chat_id,
                display_name=_bot_user_display_name(row),
                username=row.username,
            )
            for row in sample_result.all()
        ],
    )


async def create_broadcast_campaign(
    session: AsyncSession,
    *,
    title: str,
    message_text: str,
    created_by_user_id: int | None,
    audience: str = BROADCAST_AUDIENCE_ALL_BOT_USERS,
    bot_user_ids: list[int] | None = None,
    rate_limit_per_second: int = 10,
) -> BroadcastCampaign:
    recipient_query = _recipient_query(audience=audience, bot_user_ids=bot_user_ids)
    title = title.strip()
    message_text = message_text.strip()
    if not title:
        raise ValidationError("Broadcast title is required")
    if not message_text:
        raise ValidationError("Broadcast message is required")

    now = utc_now()
    campaign = BroadcastCampaign(
        title=title,
        message_text=message_text,
        audience=audience,
        status=BROADCAST_STATUS_DRAFT,
        rate_limit_per_second=rate_limit_per_second,
        created_by_user_id=created_by_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(campaign)
    await session.flush()

    result = await session.execute(recipient_query)
    recipients = [
        BroadcastRecipient(
            campaign_id=campaign.id,
            bot_user_id=row.id,
            chat_id=row.chat_id,
            display_name=_bot_user_display_name(row),
            username=row.username,
            status=RECIPIENT_STATUS_PENDING,
            created_at=now,
            updated_at=now,
        )
        for row in result.all()
    ]
    session.add_all(recipients)
    campaign.recipient_count = len(recipients)
    campaign.updated_at = now
    await session.flush()
    return campaign


async def list_broadcast_audience_users(
    session: AsyncSession,
    *,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[BroadcastAudienceUser], int]:
    query = _audience_users_query(search=search)
    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    items_result = await session.execute(query.limit(limit).offset(offset))
    admin_chat_ids = _platform_admin_chat_ids()
    return [
        BroadcastAudienceUser(
            bot_user_id=row.id,
            chat_id=row.chat_id,
            display_name=_bot_user_display_name(row),
            username=row.username,
            is_platform_admin=row.chat_id in admin_chat_ids,
        )
        for row in items_result.all()
    ], total_result.scalar_one()


async def queue_broadcast_campaign(
    session: AsyncSession,
    *,
    campaign_id: int,
    confirmation_text: str,
    task_id: str | None = None,
) -> BroadcastCampaign:
    if confirmation_text != CONFIRMATION_TEXT:
        raise ValidationError("Broadcast confirmation text is invalid")

    campaign = await session.get(BroadcastCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Broadcast campaign not found")
    if campaign.status != BROADCAST_STATUS_DRAFT:
        raise ValidationError("Only draft broadcasts can be queued")
    if campaign.recipient_count <= 0:
        raise ValidationError("Broadcast has no recipients")

    now = utc_now()
    campaign.status = BROADCAST_STATUS_QUEUED
    campaign.queued_at = now
    campaign.updated_at = now
    campaign.last_task_id = task_id
    await session.flush()
    return campaign


async def list_broadcast_campaigns(
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[BroadcastCampaign], int]:
    total_result = await session.execute(select(func.count()).select_from(BroadcastCampaign))
    items_result = await session.execute(
        select(BroadcastCampaign)
        .order_by(BroadcastCampaign.created_at.desc(), BroadcastCampaign.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(items_result.scalars().all()), total_result.scalar_one()


async def get_broadcast_campaign(
    session: AsyncSession,
    campaign_id: int,
) -> BroadcastCampaign:
    campaign = await session.get(BroadcastCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Broadcast campaign not found")
    return campaign


async def list_broadcast_recipients(
    session: AsyncSession,
    *,
    campaign_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BroadcastRecipient], int]:
    await get_broadcast_campaign(session, campaign_id)
    total_result = await session.execute(
        select(func.count()).select_from(BroadcastRecipient).where(BroadcastRecipient.campaign_id == campaign_id)
    )
    items_result = await session.execute(
        select(BroadcastRecipient)
        .where(BroadcastRecipient.campaign_id == campaign_id)
        .order_by(BroadcastRecipient.id)
        .limit(limit)
        .offset(offset)
    )
    return list(items_result.scalars().all()), total_result.scalar_one()


async def deliver_broadcast_campaign(
    session: AsyncSession,
    *,
    campaign_id: int,
    send_message: SendMessage,
    sleep: Sleep = asyncio.sleep,
) -> dict[str, int | str]:
    campaign = await session.get(BroadcastCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Broadcast campaign not found")
    if campaign.status not in {BROADCAST_STATUS_QUEUED, BROADCAST_STATUS_SENDING}:
        return {"status": "skipped", "sent": campaign.sent_count, "failed": campaign.failed_count}

    now = utc_now()
    if campaign.status == BROADCAST_STATUS_QUEUED:
        campaign.status = BROADCAST_STATUS_SENDING
        campaign.started_at = now
        campaign.updated_at = now
        await session.commit()

    sent = 0
    failed = 0
    delay_seconds = 1 / max(campaign.rate_limit_per_second or 1, 1)

    recipients_result = await session.execute(
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.campaign_id == campaign_id,
            BroadcastRecipient.status == RECIPIENT_STATUS_PENDING,
        )
        .order_by(BroadcastRecipient.id)
    )
    recipients = list(recipients_result.scalars().all())

    for recipient in recipients:
        try:
            provider_message_id = await send_message(recipient.chat_id, campaign.message_text)
            recipient.status = RECIPIENT_STATUS_SENT
            recipient.provider_message_id = provider_message_id
            recipient.error_message = None
            recipient.sent_at = utc_now()
            sent += 1
        except Exception as exc:  # noqa: BLE001 - delivery failures must be stored per recipient.
            recipient.status = RECIPIENT_STATUS_FAILED
            recipient.error_message = str(exc)[:2000]
            failed += 1
        recipient.updated_at = utc_now()
        await _refresh_campaign_counts(session, campaign)
        await session.commit()
        await sleep(delay_seconds)

    await session.refresh(campaign)
    campaign.status = BROADCAST_STATUS_COMPLETED
    campaign.completed_at = utc_now()
    campaign.updated_at = campaign.completed_at
    await _refresh_campaign_counts(session, campaign)
    await session.commit()
    return {"status": campaign.status, "sent": campaign.sent_count, "failed": campaign.failed_count}


async def mark_broadcast_failed(
    session: AsyncSession,
    *,
    campaign_id: int,
) -> None:
    campaign = await session.get(BroadcastCampaign, campaign_id)
    if campaign is None:
        return
    campaign.status = BROADCAST_STATUS_FAILED
    campaign.completed_at = utc_now()
    campaign.updated_at = campaign.completed_at
    await session.commit()


async def _refresh_campaign_counts(session: AsyncSession, campaign: BroadcastCampaign) -> None:
    counts_result = await session.execute(
        select(BroadcastRecipient.status, func.count(BroadcastRecipient.id))
        .where(BroadcastRecipient.campaign_id == campaign.id)
        .group_by(BroadcastRecipient.status)
    )
    counts = {status: count for status, count in counts_result.all()}
    campaign.sent_count = counts.get(RECIPIENT_STATUS_SENT, 0)
    campaign.failed_count = counts.get(RECIPIENT_STATUS_FAILED, 0)
    campaign.skipped_count = counts.get("skipped", 0)
    campaign.updated_at = utc_now()


def _recipient_query(*, audience: str, bot_user_ids: list[int] | None = None):
    _validate_audience(audience, bot_user_ids=bot_user_ids)
    query = _bot_user_select().where(BotUser.is_bot.is_(False))
    if audience == BROADCAST_AUDIENCE_PLATFORM_ADMINS:
        query = query.where(BotUser.chat_id.in_(_platform_admin_chat_ids()))
    if audience == BROADCAST_AUDIENCE_SELECTED_BOT_USERS:
        query = query.where(BotUser.id.in_(set(bot_user_ids or [])))
    return query.order_by(BotUser.id)


def _audience_users_query(*, search: str | None = None):
    query = _bot_user_select().where(BotUser.is_bot.is_(False))
    search = (search or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                BotUser.username.ilike(pattern),
                BotUser.first_name.ilike(pattern),
                BotUser.last_name.ilike(pattern),
                cast(BotUser.chat_id, String).ilike(pattern),
            )
        )
    return query.order_by(BotUser.id)


def _bot_user_select():
    return (
        select(
            BotUser.id,
            BotUser.chat_id,
            BotUser.username,
            BotUser.first_name,
            BotUser.last_name,
        )
    )


def _bot_user_display_name(row) -> str | None:
    parts = [part for part in (row.first_name, row.last_name) if part]
    return " ".join(parts) if parts else None


def _validate_audience(audience: str, *, bot_user_ids: list[int] | None = None) -> None:
    if audience not in {
        BROADCAST_AUDIENCE_ALL_BOT_USERS,
        BROADCAST_AUDIENCE_PLATFORM_ADMINS,
        BROADCAST_AUDIENCE_SELECTED_BOT_USERS,
    }:
        raise ValidationError("Unsupported broadcast audience")
    if audience == BROADCAST_AUDIENCE_SELECTED_BOT_USERS and not bot_user_ids:
        raise ValidationError("Selected broadcast audience requires at least one recipient")


def _platform_admin_chat_ids() -> set[int]:
    return {int(admin_id) for admin_id in config.ADMINS}
