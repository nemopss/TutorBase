"""Celery tasks for tenant access lifecycle maintenance."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import config
from services.tenant_access_service import sync_expired_access_states
from utils.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="utils.tasks.tenant_access.sync_lifecycle",
    max_retries=3,
    default_retry_delay=60,
    time_limit=120,
    soft_time_limit=90,
)
def sync_tenant_access_lifecycle_task(self) -> dict:
    logger.info(
        "Starting tenant access lifecycle sync",
        extra={"task_id": self.request.id},
    )
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_sync_tenant_access_lifecycle_async())
        finally:
            loop.close()

        logger.info(
            "Tenant access lifecycle sync completed",
            extra={"task_id": self.request.id, "result": result},
        )
        return result
    except Exception as exc:
        logger.error(
            "Tenant access lifecycle sync failed: %s",
            exc,
            extra={"task_id": self.request.id, "retry_count": self.request.retries},
            exc_info=True,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        raise


async def _sync_tenant_access_lifecycle_async() -> dict:
    task_engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    task_session = async_sessionmaker(task_engine, expire_on_commit=False)

    try:
        async with task_session() as session:
            result = await sync_expired_access_states(session)
            await session.commit()
            return {
                "status": "success",
                "grace_started": result.grace_started,
                "expired": result.expired,
                "changed": result.changed,
            }
    finally:
        await task_engine.dispose()


__all__ = ["sync_tenant_access_lifecycle_task"]
