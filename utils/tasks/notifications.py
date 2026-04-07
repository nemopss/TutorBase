"""Celery tasks for the new notification bounded context."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import config
from database.models import Tenant
from notifications.application.delivery import (
    ClaimDueNotificationsUseCase,
    ExecuteClaimedNotificationDeliveryUseCase,
)
from notifications.application.dto import NotificationJobRecord
from notifications.application.jobs import ClaimQueuedNotificationJobsUseCase
from notifications.application.materialization import RunMaterializeActiveRulesJobUseCase
from notifications.application.reconciliation import (
    RunReconcileNotificationEventJobUseCase,
    RunReconcileNotificationGroupMembershipJobUseCase,
)
from notifications.infrastructure.rendering import SqlAlchemyNotificationRenderer
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork
from notifications.infrastructure.telegram_delivery import TelegramNotificationChannelAdapter
from utils.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="utils.tasks.notifications.process_notification_jobs",
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=540,
)
def process_notification_jobs_task(
    self,
    tenant_id: Optional[int] = None,
    job_type: Optional[str] = None,
    limit: int = 20,
) -> dict:
    logger.info(
        "Starting notification job processing tick",
        extra={
            "tenant_id": tenant_id,
            "job_type": job_type,
            "limit": limit,
            "task_id": self.request.id,
        },
    )
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _process_notification_jobs_async(tenant_id, job_type, limit)
            )
        finally:
            loop.close()

        logger.info(
            "Notification job processing tick completed",
            extra={
                "tenant_id": tenant_id,
                "job_type": job_type,
                "result": result,
                "task_id": self.request.id,
            },
        )
        return result
    except Exception as exc:
        logger.error(
            "Notification job processing tick failed: %s",
            exc,
            extra={
                "tenant_id": tenant_id,
                "job_type": job_type,
                "limit": limit,
                "task_id": self.request.id,
                "retry_count": self.request.retries,
            },
            exc_info=True,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        raise


@celery_app.task(
    bind=True,
    name="utils.tasks.notifications.deliver_due_notifications",
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def deliver_due_notifications_task(
    self,
    tenant_id: Optional[int] = None,
    limit: int = 100,
) -> dict:
    logger.info(
        "Starting notification delivery tick",
        extra={"tenant_id": tenant_id, "limit": limit, "task_id": self.request.id},
    )
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_deliver_due_notifications_async(tenant_id, limit))
        finally:
            loop.close()

        logger.info(
            "Notification delivery tick completed",
            extra={"tenant_id": tenant_id, "result": result, "task_id": self.request.id},
        )
        return result
    except Exception as exc:
        logger.error(
            "Notification delivery tick failed: %s",
            exc,
            extra={
                "tenant_id": tenant_id,
                "limit": limit,
                "task_id": self.request.id,
                "retry_count": self.request.retries,
            },
            exc_info=True,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        raise


async def _process_notification_jobs_async(
    tenant_id: int | None,
    job_type: str | None,
    limit: int,
) -> dict:
    task_engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    task_session = async_sessionmaker(task_engine, expire_on_commit=False)

    try:
        async with task_session() as session:
            tenant_ids = (tenant_id,) if tenant_id is not None else await _active_tenant_ids(session)
            totals = {"tenants": 0, "claimed": 0, "succeeded": 0, "failed": 0}
            job_types = (
                (job_type,)
                if job_type
                else (
                    "reconcile_event",
                    "reconcile_group_membership",
                    "materialize_active_rules",
                )
            )
            for current_tenant_id in tenant_ids:
                for current_job_type in job_types:
                    summary = await _process_jobs_for_tenant(
                        session,
                        tenant_id=current_tenant_id,
                        job_type=current_job_type,
                        limit=limit,
                    )
                    totals["claimed"] += summary["claimed"]
                    totals["succeeded"] += summary["succeeded"]
                    totals["failed"] += summary["failed"]
                totals["tenants"] += 1
            return {"status": "success", "job_type": job_type or "all", **totals}
    finally:
        await task_engine.dispose()


async def _deliver_due_notifications_async(tenant_id: int | None, limit: int) -> dict:
    task_engine = create_async_engine(
        config.build_async_database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    task_session = async_sessionmaker(task_engine, expire_on_commit=False)
    bot = Bot(token=config.BOT_TOKEN)

    try:
        async with task_session() as session:
            tenant_ids = (tenant_id,) if tenant_id is not None else await _active_tenant_ids(session)
            totals = {"tenants": 0, "claimed": 0, "sent": 0, "failed": 0}
            for current_tenant_id in tenant_ids:
                summary = await _deliver_for_tenant(
                    session,
                    bot=bot,
                    tenant_id=current_tenant_id,
                    limit=limit,
                )
                totals["tenants"] += 1
                totals["claimed"] += summary["claimed"]
                totals["sent"] += summary["sent"]
                totals["failed"] += summary["failed"]
            return {"status": "success", **totals}
    finally:
        await bot.session.close()
        await task_engine.dispose()


async def _active_tenant_ids(session) -> tuple[int, ...]:
    result = await session.execute(
        select(Tenant.id).where(Tenant.is_active.is_(True)).order_by(Tenant.id)
    )
    return tuple(result.scalars())


async def _process_jobs_for_tenant(
    session,
    *,
    tenant_id: int,
    job_type: str,
    limit: int,
) -> dict:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    claim_result = await ClaimQueuedNotificationJobsUseCase(uow).execute(
        job_type=job_type,
        limit=limit,
    )

    succeeded = 0
    failed = 0
    for job in claim_result.claimed:
        try:
            await _run_claimed_job(uow, job)
            succeeded += 1
        except Exception as exc:
            logger.error(
                "Notification job failed: %s",
                exc,
                extra={
                    "tenant_id": tenant_id,
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                },
                exc_info=True,
            )
            await uow.rollback()
            failure_uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
            await failure_uow.jobs.mark_failed(job.job_id, error=str(exc))
            await failure_uow.commit()
            failed += 1

    return {
        "tenant_id": tenant_id,
        "job_type": job_type,
        "claimed": len(claim_result.claimed),
        "succeeded": succeeded,
        "failed": failed,
    }


async def _run_claimed_job(uow, job: NotificationJobRecord) -> None:
    if job.job_type == "materialize_active_rules":
        await RunMaterializeActiveRulesJobUseCase(uow).execute(job)
        return
    if job.job_type == "reconcile_event":
        await RunReconcileNotificationEventJobUseCase(uow).execute(job)
        return
    if job.job_type == "reconcile_group_membership":
        await RunReconcileNotificationGroupMembershipJobUseCase(uow).execute(job)
        return
    raise ValueError(f"Unsupported notification job type: {job.job_type}")


async def _deliver_for_tenant(
    session,
    *,
    bot: Bot,
    tenant_id: int,
    limit: int,
) -> dict:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    claim_result = await ClaimDueNotificationsUseCase(uow).execute(limit=limit)
    renderer = SqlAlchemyNotificationRenderer(session, tenant_id=tenant_id)
    adapter = TelegramNotificationChannelAdapter(bot)

    sent = 0
    failed = 0
    for claimed in claim_result.claimed:
        result = await ExecuteClaimedNotificationDeliveryUseCase(
            uow,
            renderer=renderer,
            channel_adapter=adapter,
        ).execute(claimed)
        if result.status.value == "sent":
            sent += 1
        else:
            failed += 1

    return {
        "tenant_id": tenant_id,
        "claimed": len(claim_result.claimed),
        "sent": sent,
        "failed": failed,
    }


__all__ = ["deliver_due_notifications_task", "process_notification_jobs_task"]
