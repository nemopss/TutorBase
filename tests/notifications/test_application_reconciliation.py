from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from notifications.application.dto import (
    AudienceSelector,
    InstanceUpsertResult,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationInstanceDraft,
    NotificationRuleDraft,
    NotificationSettingsRecord,
    PreviewEvent,
    PreviewRecipient,
)
from notifications.application.reconciliation import (
    QueueNotificationEventReconciliationUseCase,
    QueueNotificationGroupMembershipReconciliationUseCase,
    RunReconcileNotificationEventJobUseCase,
    RunReconcileNotificationGroupMembershipJobUseCase,
)
from notifications.domain.enums import (
    CategoryKey,
    EventType,
    InstanceStatus,
    NotificationSystemMode,
    Priority,
    TriggerType,
)


@dataclass
class FakeAudienceResolver:
    recipients: tuple[PreviewRecipient, ...]

    async def resolve_recipients(self, assignments):
        return self.recipients


@dataclass
class FakeEventRepository:
    event: PreviewEvent | None

    async def list_events_for_recipients(self, *, event_type, learner_ids, horizon_days, limit):
        if self.event is None:
            return ()
        if self.event.event_type != event_type or self.event.learner_id not in set(learner_ids):
            return ()
        return (self.event,)

    async def get_event(self, *, event_type, event_id):
        if self.event is None:
            return None
        if self.event.event_type == event_type and self.event.event_id == event_id:
            return self.event
        return None


class FakePreferenceRepository:
    async def get_global_preference(self):
        return None

    async def get_group_preferences_for_learner(self, learner_id):
        return ()

    async def get_learner_preference(self, learner_id):
        return None


@dataclass
class FakeRuleRepository:
    rules: tuple[NotificationRuleDraft, ...]

    async def list_active_rules(self):
        return self.rules

    async def list_active_rules_for_group(self, group_id):
        return tuple(
            rule
            for rule in self.rules
            if any(
                assignment.scope_type == "group"
                and assignment.scope_id == group_id
                and not assignment.is_exclusion
                for assignment in rule.assignments
            )
        )


@dataclass
class FakeInstanceRepository:
    cancelled: list[dict] = field(default_factory=list)
    upserted: tuple[NotificationInstanceDraft, ...] = ()

    async def cancel_future_instances_for_event(self, *, event_type, event_id, reason):
        self.cancelled.append({"event_type": event_type, "event_id": event_id, "reason": reason})
        return 2

    async def cancel_future_instances_for_rules_and_learners(self, *, rule_ids, learner_ids, reason):
        self.cancelled.append({"rule_ids": rule_ids, "learner_ids": learner_ids, "reason": reason})
        return 3

    async def upsert_planned_instances(self, instances):
        self.upserted = instances
        return InstanceUpsertResult(planned_count=len(instances), upserted_count=len(instances))


@dataclass
class FakeJobRepository:
    records: list[NotificationJobRecord] = field(default_factory=list)
    succeeded: list[dict] = field(default_factory=list)

    async def create_job(self, draft: NotificationJobDraft):
        record = NotificationJobRecord(
            job_id=1,
            job_type=draft.job_type,
            status="queued",
            scope=draft.scope,
        )
        self.records.append(record)
        return record

    async def mark_succeeded(self, job_id: int, *, result_summary: dict):
        self.succeeded.append(result_summary)
        record = NotificationJobRecord(
            job_id=job_id,
            job_type=self.records[-1].job_type,
            status="succeeded",
            scope=self.records[-1].scope,
        )
        self.records.append(record)
        return record


@dataclass
class FakeSettingsRepository:
    mode: NotificationSystemMode = NotificationSystemMode.SHADOW

    async def get_settings(self):
        return NotificationSettingsRecord(tenant_id=1, mode=self.mode)


@dataclass
class FakeUnitOfWork:
    audience_resolver: FakeAudienceResolver
    events: FakeEventRepository
    rules: FakeRuleRepository
    instances: FakeInstanceRepository = field(default_factory=FakeInstanceRepository)
    jobs: FakeJobRepository = field(default_factory=FakeJobRepository)
    preferences: FakePreferenceRepository = field(default_factory=FakePreferenceRepository)
    responses: object | None = None
    groups: object | None = None
    templates: object | None = None
    settings: FakeSettingsRepository = field(default_factory=FakeSettingsRepository)
    committed: bool = False

    async def commit(self):
        self.committed = True


def _event() -> PreviewEvent:
    return PreviewEvent(
        event_type=EventType.LESSON,
        event_id=617,
        learner_id=10,
        starts_at=datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc),
        timezone="UTC",
        package_status="active",
        lesson_status="scheduled",
        has_homework=True,
    )


def _rule() -> NotificationRuleDraft:
    return NotificationRuleDraft(
        rule_id=1,
        name="Подтверждение",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation_day_before_ru",
        assignments=(AudienceSelector(scope_type="learner", scope_id=10),),
    )


def _group_rule() -> NotificationRuleDraft:
    return NotificationRuleDraft(
        rule_id=2,
        name="Группа TOPIK",
        category=CategoryKey.HOMEWORK,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Домашка для {student_name}",
        template_key="homework_before_lesson_ru",
        assignments=(AudienceSelector(scope_type="group", scope_id=7),),
    )


def _uow(*, event: PreviewEvent | None = None) -> FakeUnitOfWork:
    return FakeUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(PreviewRecipient(learner_id=10, display_name="Вика"),)
        ),
        events=FakeEventRepository(event=event),
        rules=FakeRuleRepository(rules=(_rule(),)),
    )


@pytest.mark.asyncio
async def test_queue_event_reconciliation_creates_durable_shadow_job():
    uow = _uow(event=_event())

    job = await QueueNotificationEventReconciliationUseCase(uow).execute(
        event_type=EventType.LESSON,
        event_id=617,
        reason="lesson_updated",
        created_by_user_id=42,
    )

    assert uow.committed
    assert job.job_type == "reconcile_event"
    assert job.scope["event_type"] == "lesson"
    assert job.scope["event_id"] == 617
    assert job.scope["reason"] == "lesson_updated"
    assert job.scope["shadow"] is True
    assert job.scope["delivery_enabled"] is False


@pytest.mark.asyncio
async def test_queue_group_membership_reconciliation_uses_effective_shadow_mode():
    uow = _uow(event=_event())

    job = await QueueNotificationGroupMembershipReconciliationUseCase(uow).execute(
        group_id=7,
        learner_ids=(11, 10, 10),
        reason="group_members_added",
        created_by_user_id=42,
    )

    assert uow.committed
    assert job.job_type == "reconcile_group_membership"
    assert job.scope["group_id"] == 7
    assert job.scope["learner_ids"] == [10, 11]
    assert job.scope["reason"] == "group_members_added"
    assert job.scope["shadow"] is True
    assert job.scope["delivery_enabled"] is False


@pytest.mark.asyncio
async def test_run_event_reconciliation_cancels_stale_instances_and_upserts_scoped_event():
    uow = _uow(event=_event())
    job = NotificationJobRecord(
        job_id=7,
        job_type="reconcile_event",
        status="running",
        scope={
            "event_type": "lesson",
            "event_id": 617,
            "reason": "lesson_updated",
            "shadow": True,
            "delivery_enabled": False,
        },
    )
    uow.jobs.records.append(job)

    result = await RunReconcileNotificationEventJobUseCase(uow).execute(job)

    assert uow.committed
    assert result.event_found is True
    assert result.cancelled_count == 2
    assert uow.instances.cancelled == [
        {
            "event_type": EventType.LESSON,
            "event_id": 617,
            "reason": "reconciled:lesson_updated",
        }
    ]
    assert len(uow.instances.upserted) == 1
    assert uow.instances.upserted[0].event_id == 617
    assert uow.instances.upserted[0].status == InstanceStatus.SHADOW
    assert uow.jobs.succeeded[-1]["event_found"] is True


@pytest.mark.asyncio
async def test_run_event_reconciliation_marks_missing_event_as_success_after_cancellation():
    uow = _uow(event=None)
    job = NotificationJobRecord(
        job_id=7,
        job_type="reconcile_event",
        status="running",
        scope={"event_type": "lesson", "event_id": 617},
    )
    uow.jobs.records.append(job)

    result = await RunReconcileNotificationEventJobUseCase(uow).execute(job)

    assert uow.committed
    assert result.event_found is False
    assert result.materialization.warnings == ("event_not_found",)
    assert uow.instances.upserted == ()
    assert uow.jobs.succeeded[-1]["event_found"] is False


@pytest.mark.asyncio
async def test_run_group_membership_reconciliation_cancels_and_materializes_scoped_learners():
    uow = FakeUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(
                PreviewRecipient(learner_id=10, display_name="Вика"),
                PreviewRecipient(learner_id=11, display_name="Иван"),
            )
        ),
        events=FakeEventRepository(event=_event()),
        rules=FakeRuleRepository(rules=(_group_rule(),)),
    )
    job = NotificationJobRecord(
        job_id=8,
        job_type="reconcile_group_membership",
        status="running",
        scope={
            "group_id": 7,
            "learner_ids": [10],
            "reason": "group_members_added",
            "shadow": True,
            "delivery_enabled": False,
        },
    )
    uow.jobs.records.append(job)

    result = await RunReconcileNotificationGroupMembershipJobUseCase(uow).execute(job)

    assert uow.committed
    assert result.group_id == 7
    assert result.learner_ids == (10,)
    assert result.rules_count == 1
    assert result.cancelled_count == 3
    assert uow.instances.cancelled == [
        {
            "rule_ids": (2,),
            "learner_ids": (10,),
            "reason": "reconciled:group_members_added",
        }
    ]
    assert len(uow.instances.upserted) == 1
    assert uow.instances.upserted[0].learner_id == 10
    assert uow.instances.upserted[0].status == InstanceStatus.SHADOW
    assert uow.jobs.succeeded[-1]["group_id"] == 7
    assert uow.jobs.succeeded[-1]["rules_count"] == 1
