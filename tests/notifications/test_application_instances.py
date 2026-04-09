from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from notifications.application.dto import (
    NotificationActivityRecord,
    NotificationAuditLogDraft,
    NotificationInstanceRecord,
)
from notifications.application.instances import (
    CancelNotificationInstanceUseCase,
    GetNotificationInstanceUseCase,
    ListNotificationActivityUseCase,
    ListNotificationInstancesUseCase,
    ScheduleNotificationInstanceNowUseCase,
)
from notifications.domain.enums import CategoryKey, EventType, InstanceStatus, Priority


@dataclass
class FakeInstanceRepository:
    instances: tuple[NotificationInstanceRecord, ...]
    activity: tuple[NotificationActivityRecord, ...]
    cancelled: list[tuple[int, str | None]] = field(default_factory=list)
    scheduled_now: list[tuple[int, datetime]] = field(default_factory=list)
    last_list_kwargs: dict[str, object] = field(default_factory=dict)

    async def list_instances(
        self,
        *,
        status=None,
        statuses=None,
        learner_id=None,
        event_type=None,
        scheduled_from=None,
        scheduled_to=None,
        limit=100,
    ):
        self.last_list_kwargs = {
            "status": status,
            "statuses": statuses,
            "learner_id": learner_id,
            "event_type": event_type,
            "scheduled_from": scheduled_from,
            "scheduled_to": scheduled_to,
            "limit": limit,
        }
        return self.instances[:limit]

    async def get_instance(self, instance_id):
        return next((instance for instance in self.instances if instance.instance_id == instance_id), None)

    async def list_activity(self, *, learner_id=None, limit=100):
        return self.activity[:limit]

    async def cancel_instance(self, instance_id, *, reason=None):
        self.cancelled.append((instance_id, reason))
        return next((instance for instance in self.instances if instance.instance_id == instance_id), None)

    async def schedule_instance_now(self, instance_id, *, now):
        self.scheduled_now.append((instance_id, now))
        return next((instance for instance in self.instances if instance.instance_id == instance_id), None)


@dataclass
class FakeUnitOfWork:
    instances: FakeInstanceRepository
    audit_log: "FakeAuditLogRepository" = field(default_factory=lambda: FakeAuditLogRepository())
    committed: bool = False

    async def commit(self):
        self.committed = True


@dataclass
class FakeAuditLogRepository:
    records: list[NotificationAuditLogDraft] = field(default_factory=list)

    async def record_audit(self, draft):
        self.records.append(draft)
        return None


def _instance() -> NotificationInstanceRecord:
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    return NotificationInstanceRecord(
        instance_id=1,
        rule_id=10,
        category=CategoryKey.HOMEWORK,
        event_type=EventType.LESSON,
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=5,
        learner_id=5,
        learner_display_name="Вика",
        scheduled_for=now,
        effective_scheduled_for=now,
        status=InstanceStatus.SCHEDULED,
        status_reason=None,
        delivery_enabled=True,
        priority=Priority.NORMAL,
        channel="telegram",
        dedupe_key="single|homework|rule:10|2026-04-08T07:00:00+00:00",
        combination_key=None,
    )


@pytest.mark.asyncio
async def test_list_and_get_instances_use_cases():
    instance = _instance()
    repository = FakeInstanceRepository(instances=(instance,), activity=())
    uow = FakeUnitOfWork(instances=repository)

    listed = await ListNotificationInstancesUseCase(uow).execute(status=InstanceStatus.SCHEDULED)
    fetched = await GetNotificationInstanceUseCase(uow).execute(1)

    assert listed == (instance,)
    assert fetched == instance
    assert repository.last_list_kwargs["status"] == InstanceStatus.SCHEDULED.value
    assert repository.last_list_kwargs["statuses"] is None


@pytest.mark.asyncio
async def test_list_instances_use_case_supports_multiple_statuses():
    instance = _instance()
    repository = FakeInstanceRepository(instances=(instance,), activity=())
    uow = FakeUnitOfWork(instances=repository)

    listed = await ListNotificationInstancesUseCase(uow).execute(
        statuses=(InstanceStatus.SCHEDULED, InstanceStatus.SHADOW),
    )

    assert listed == (instance,)
    assert repository.last_list_kwargs["status"] is None
    assert repository.last_list_kwargs["statuses"] == (
        InstanceStatus.SCHEDULED.value,
        InstanceStatus.SHADOW.value,
    )


@pytest.mark.asyncio
async def test_list_activity_use_case():
    activity = NotificationActivityRecord(
        activity_type="response",
        activity_id=1,
        notification_instance_id=1,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        learner_id=5,
        learner_display_name="Вика",
        status="confirmed",
        action_key="confirm_lesson",
        response_value="confirmed",
        occurred_at=datetime(2026, 4, 8, 7, 1, tzinfo=timezone.utc),
    )
    uow = FakeUnitOfWork(instances=FakeInstanceRepository(instances=(), activity=(activity,)))

    result = await ListNotificationActivityUseCase(uow).execute(learner_id=5)

    assert result == (activity,)


@pytest.mark.asyncio
async def test_cancel_and_send_now_use_cases_commit_state_transitions():
    instance = _instance()
    repository = FakeInstanceRepository(instances=(instance,), activity=())
    uow = FakeUnitOfWork(instances=repository)
    now = datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc)

    cancelled = await CancelNotificationInstanceUseCase(uow).execute(1, reason="manual")
    scheduled_now = await ScheduleNotificationInstanceNowUseCase(uow).execute(1, now=now)

    assert cancelled == instance
    assert scheduled_now == instance
    assert repository.cancelled == [(1, "manual")]
    assert repository.scheduled_now == [(1, now)]
    assert [record.action for record in uow.audit_log.records] == [
        "cancelled",
        "send_now_scheduled",
    ]
    assert uow.audit_log.records[0].reason == "manual"
    assert uow.committed is True
