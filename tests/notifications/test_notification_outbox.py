from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from notifications.application.dto import NotificationJobDraft
from notifications.infrastructure.models import NotificationJob
from notifications.infrastructure.repositories import SqlAlchemyNotificationJobRepository


@pytest.mark.asyncio
async def test_notification_outbox_coalesces_queued_event_changes(db_session, current_tenant):
    repository = SqlAlchemyNotificationJobRepository(
        db_session,
        tenant_id=current_tenant.tenant_id,
    )
    first = await repository.create_job(
        NotificationJobDraft(
            job_type="reconcile_event",
            dedupe_key="reconcile_event:lesson:42",
            scope={"event_type": "lesson", "event_id": 42, "reason": "lesson_created"},
        )
    )
    second = await repository.create_job(
        NotificationJobDraft(
            job_type="reconcile_event",
            dedupe_key="reconcile_event:lesson:42",
            scope={"event_type": "lesson", "event_id": 42, "reason": "lesson_updated"},
        )
    )

    count = await db_session.scalar(
        select(func.count(NotificationJob.id)).where(
            NotificationJob.tenant_id == current_tenant.tenant_id,
            NotificationJob.dedupe_key == "reconcile_event:lesson:42",
        )
    )
    job = await db_session.get(NotificationJob, first.job_id)
    assert second.job_id == first.job_id
    assert count == 1
    assert job.scope["reason"] == "lesson_updated"


@pytest.mark.asyncio
async def test_notification_outbox_retries_with_backoff(db_session, current_tenant):
    now = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
    repository = SqlAlchemyNotificationJobRepository(
        db_session,
        tenant_id=current_tenant.tenant_id,
        now_factory=lambda: now,
    )
    queued = await repository.create_job(
        NotificationJobDraft(
            job_type="reconcile_event",
            dedupe_key="reconcile_event:package:77",
            scope={"event_type": "package", "event_id": 77},
        )
    )
    claimed = await repository.claim_queued_jobs(job_type="reconcile_event", limit=10)
    retried = await repository.mark_failed(
        queued.job_id,
        error="temporary database error",
        retryable=True,
    )
    job = await db_session.get(NotificationJob, queued.job_id)

    assert claimed[0].attempt_count == 1
    assert retried.status == "queued"
    assert job.available_at > now
    assert job.error == "temporary database error"
