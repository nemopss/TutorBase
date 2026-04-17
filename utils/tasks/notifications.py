"""Celery tasks for the new notification bounded context."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aiogram import Bot
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import config
from database.models import Learner, Lesson, Tenant
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
from notifications.infrastructure.models import NotificationCategory, NotificationInstance
from notifications.infrastructure.rendering import SqlAlchemyNotificationRenderer
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork
from notifications.infrastructure.telegram_delivery import TelegramNotificationChannelAdapter
from utils.celery_app import celery_app
from utils.formatters import escape_html_text, format_timestamp_msk
from utils.telegram_bot import build_telegram_bot


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationDeliveryLogContext:
    learner_name: str
    category_name: str
    event_type: str
    lesson_scheduled_at: datetime | None = None


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
    bot = build_telegram_bot()

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
            await _send_delivery_log(
                session,
                bot=bot,
                tenant_id=tenant_id,
                instance_id=claimed.instance_id,
                provider_message_id=result.provider_message_id,
            )
        else:
            failed += 1

    return {
        "tenant_id": tenant_id,
        "claimed": len(claim_result.claimed),
        "sent": sent,
        "failed": failed,
    }


async def _send_delivery_log(
    session,
    *,
    bot: Bot,
    tenant_id: int,
    instance_id: int,
    provider_message_id: str | None,
) -> None:
    context = await _delivery_log_context(session, tenant_id=tenant_id, instance_id=instance_id)
    if context is None:
        logger.warning("Delivery log context not found for notification instance #%s", instance_id)
        return
    try:
        await bot.send_message(
            config.LOGS_CHAT_ID,
            _build_delivery_log_message(
                context,
                provider_message_id=provider_message_id,
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send notification delivery log for instance #%s: %s", instance_id, exc)


async def _delivery_log_context(
    session,
    *,
    tenant_id: int,
    instance_id: int,
) -> NotificationDeliveryLogContext | None:
    result = await session.execute(
        select(
            Learner.display_name.label("learner_name"),
            NotificationCategory.display_name.label("category_name"),
            NotificationInstance.event_type,
            Lesson.scheduled_at.label("lesson_scheduled_at"),
        )
        .select_from(NotificationInstance)
        .outerjoin(Learner, Learner.id == NotificationInstance.learner_id)
        .outerjoin(NotificationCategory, NotificationCategory.id == NotificationInstance.category_id)
        .outerjoin(
            Lesson,
            and_(
                NotificationInstance.event_type == "lesson",
                Lesson.id == NotificationInstance.event_id,
            ),
        )
        .where(
            NotificationInstance.tenant_id == tenant_id,
            NotificationInstance.id == instance_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    return NotificationDeliveryLogContext(
        learner_name=row.learner_name or "Ученик",
        category_name=row.category_name or "Уведомление",
        event_type=row.event_type,
        lesson_scheduled_at=row.lesson_scheduled_at,
    )


def _build_delivery_log_message(
    context: NotificationDeliveryLogContext,
    *,
    provider_message_id: str | None,
) -> str:
    lines = [
        "#notification_sent",
        f"Ученик: {escape_html_text(context.learner_name)}",
        f"Категория: {escape_html_text(context.category_name)}",
    ]
    if context.event_type == "lesson" and context.lesson_scheduled_at is not None:
        lines.append(
            f"Урок: {escape_html_text(format_timestamp_msk(context.lesson_scheduled_at))}"
        )
    if provider_message_id:
        lines.append(f"Telegram message_id: <code>{escape_html_text(provider_message_id)}</code>")
    mention = _log_notify_mention()
    if mention:
        lines.append(mention)
    return "\n".join(lines)


def _log_notify_mention() -> str | None:
    if not config.REMINDER_NOTIFY_USERNAME:
        return None
    return f"@{escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME)}"


__all__ = [
    "deliver_due_notifications_task",
    "process_notification_jobs_task",
    "_build_delivery_log_message",
]
