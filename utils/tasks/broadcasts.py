"""Celery tasks for platform Telegram broadcasts."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import config
from services import broadcast_service
from utils.celery_app import celery_app
from utils.telegram_bot import build_telegram_bot


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="utils.tasks.broadcasts.send_broadcast_campaign",
    max_retries=0,
    time_limit=1800,
    soft_time_limit=1740,
)
def send_broadcast_campaign_task(self, campaign_id: int) -> dict:
    logger.info(
        "Starting broadcast campaign delivery",
        extra={"campaign_id": campaign_id, "task_id": self.request.id},
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_broadcast_campaign_async(campaign_id))
    finally:
        loop.close()


async def _send_broadcast_campaign_async(campaign_id: int) -> dict:
    task_engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    task_session = async_sessionmaker(task_engine, expire_on_commit=False)
    bot = build_telegram_bot()

    async def send_message(chat_id: int, message_text: str) -> str | None:
        message = await bot.send_message(chat_id, message_text)
        message_id = getattr(message, "message_id", None)
        return str(message_id) if message_id is not None else None

    try:
        async with task_session() as session:
            try:
                result = await broadcast_service.deliver_broadcast_campaign(
                    session,
                    campaign_id=campaign_id,
                    send_message=send_message,
                )
                logger.info(
                    "Broadcast campaign delivery completed",
                    extra={"campaign_id": campaign_id, "result": result},
                )
                return result
            except Exception:
                logger.exception("Broadcast campaign delivery failed", extra={"campaign_id": campaign_id})
                await broadcast_service.mark_broadcast_failed(session, campaign_id=campaign_id)
                raise
    finally:
        await bot.session.close()
        await task_engine.dispose()


__all__ = ["send_broadcast_campaign_task"]
