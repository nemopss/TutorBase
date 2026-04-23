from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from notifications.application.dto import (
    DeliverySendResult,
    NotificationAuditLogDraft,
    NotificationJobDraft,
    NotificationInstanceComponentDraft,
    NotificationInstanceDraft,
    NotificationResponseDraft,
    RenderedNotification,
)
from notifications.domain.enums import CategoryKey, EventType, InstanceStatus, Priority
from notifications.infrastructure.models import (
    NotificationCategory,
    NotificationAuditLog,
    NotificationDeliveryAttempt,
    NotificationInstance,
    NotificationInstanceComponent,
    NotificationResponse,
)
from notifications.infrastructure.repositories import (
    SqlAlchemyNotificationInstanceRepository,
    SqlAlchemyNotificationAuditLogRepository,
    SqlAlchemyNotificationJobRepository,
    SqlAlchemyNotificationResponseRepository,
    _delivery_activity_from_row,
    _audit_log_record_from_model,
    _delivery_activity_stmt,
    _due_instances_for_claim_stmt,
    _instance_record_from_row,
    _lesson_event_by_id_stmt,
    _notification_audit_log_stmt,
    _notification_instances_stmt,
    _package_event_by_id_stmt,
    _queued_jobs_for_claim_stmt,
    _response_activity_from_row,
    _response_activity_stmt,
)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

    def __iter__(self):
        return iter(self._rows)

    def scalars(self):
        return FakeScalars(self._rows)

    def scalar_one(self):
        return self._rows[0]


class FakeRow:
    def __init__(self, first, **attrs):
        self._first = first
        for key, value in attrs.items():
            setattr(self, key, value)

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return self._first


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeUniqueFirstResult:
    def __init__(self, row):
        self.row = row

    def unique(self):
        return self

    def first(self):
        return self.row


class FakeInstanceActionSession:
    def __init__(self, instance):
        self.instance = instance
        self.flush_count = 0
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if len(self.calls) == 1:
            return FakeOneOrNoneResult(self.instance)
        return FakeUniqueFirstResult(FakeRow(self.instance, learner_display_name="Вика"))

    async def flush(self):
        self.flush_count += 1


class FakeBulkUpdateResult:
    rowcount = 3


class FakeBulkUpdateSession:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        return FakeBulkUpdateResult()


class FakeAsyncSession:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if len(self.calls) == 1:
            return FakeResult(
                [
                    SimpleNamespace(key="lesson_confirmation", id=1),
                    SimpleNamespace(key="homework", id=2),
                ]
            )
        if getattr(statement, "table", None) is NotificationInstance.__table__:
            return FakeResult(
                [
                    SimpleNamespace(
                        id=101,
                        recipient_type="learner",
                        recipient_id=10,
                        event_type="lesson",
                        event_key="lesson:617",
                        dedupe_key="combined|lesson_confirmation_homework|x",
                    )
                ]
            )
        return FakeResult([])


class FakeClaimSession:
    def __init__(self, instances, *, stale_instances=()):
        self.instances = instances
        self.stale_instances = list(stale_instances)
        self.calls = []
        self.added = []

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if len(self.calls) == 1:
            for instance in self.stale_instances:
                instance.status = "expired"
                instance.status_reason = "delivery_window_exceeded"
                instance.delivery_enabled = False
            return FakeResult([])
        if len(self.calls) == 2:
            return FakeResult(self.instances)
        if len(self.calls) <= 2 + len(self.instances):
            return FakeResult([1])
        return FakeResult([SimpleNamespace(id=10, chat_id="5390064156")])

    def add(self, model):
        model.id = len(self.added) + 201
        self.added.append(model)

    async def flush(self):
        return None


class FakeJobSession:
    def __init__(self):
        self.objects = {}
        self.next_id = 1
        self.added = []
        self.flush_count = 0

    def add(self, model):
        model.id = self.next_id
        self.next_id += 1
        self.objects[model.id] = model
        self.added.append(model)

    async def flush(self):
        self.flush_count += 1

    async def get(self, model_cls, model_id):
        return self.objects.get(model_id)


class FakeQueuedJobSession:
    def __init__(self, jobs):
        self.jobs = jobs
        self.calls = []
        self.flush_count = 0

    async def execute(self, statement, params=None):
        self.calls.append((statement, params))
        return FakeResult(self.jobs)

    async def flush(self):
        self.flush_count += 1


class FakeDeliverySession:
    def __init__(self, instance, attempt):
        self.objects = {
            (NotificationInstance, instance.id): instance,
            (NotificationDeliveryAttempt, attempt.id): attempt,
        }
        self.flush_count = 0

    async def get(self, model_cls, model_id):
        return self.objects.get((model_cls, model_id))

    async def flush(self):
        self.flush_count += 1


class FakeResponseSession:
    def __init__(self, instance):
        self.instance = instance
        self.added = []
        self.executed = []
        self.flush_count = 0

    async def get(self, model_cls, model_id):
        if model_cls is NotificationInstance and model_id == self.instance.id:
            return self.instance
        return None

    def add(self, model):
        model.id = len(self.added) + 301
        self.added.append(model)

    async def flush(self):
        self.flush_count += 1

    async def execute(self, statement, params=None):
        self.executed.append((statement, params))
        return FakeResult([])


def _planned_instance(*, components: bool = False) -> NotificationInstanceDraft:
    component_drafts = ()
    if components:
        component_drafts = (
            NotificationInstanceComponentDraft(
                rule_id=1,
                category=CategoryKey.LESSON_CONFIRMATION,
                component_key="lesson_confirmation:lesson_confirmation",
                template_key="lesson_confirmation",
            ),
            NotificationInstanceComponentDraft(
                rule_id=2,
                category=CategoryKey.HOMEWORK,
                component_key="homework:homework",
                template_key="homework",
            ),
        )

    return NotificationInstanceDraft(
        rule_id=None if components else 1,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        status=InstanceStatus.SCHEDULED,
        delivery_enabled=True,
        priority=Priority.NORMAL,
        channel="telegram",
        dedupe_key=(
            "combined|lesson_confirmation_homework|x"
            if components
            else "single|lesson_confirmation|x"
        ),
        combination_key="lesson_confirmation_homework" if components else None,
        components=component_drafts,
    )


@pytest.mark.asyncio
async def test_instance_repository_uses_postgresql_upsert_with_non_nullable_event_key():
    session = FakeAsyncSession()
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    await repository.upsert_planned_instances((_planned_instance(),))

    upsert_statement = session.calls[1][0]
    compiled = str(upsert_statement.compile(dialect=postgresql.dialect()))
    assert (
        "ON CONFLICT (tenant_id, recipient_type, recipient_id, event_type, event_key, dedupe_key)"
        in compiled
    )
    assert "event_id" not in compiled.partition("ON CONFLICT")[2].partition(")")[0]
    assert "notification_instances.status NOT IN" in compiled
    assert "notification_responses.notification_instance_id = notification_instances.id" in compiled


@pytest.mark.asyncio
async def test_instance_repository_replaces_combined_components_after_upsert():
    session = FakeAsyncSession()
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    result = await repository.upsert_planned_instances((_planned_instance(components=True),))

    assert result.planned_count == 1
    assert result.upserted_count == 1
    insert_components_params = session.calls[-1][1]
    assert len(insert_components_params) == 2
    assert [row["instance_id"] for row in insert_components_params] == [101, 101]
    assert [row["component_key"] for row in insert_components_params] == [
        "lesson_confirmation:lesson_confirmation",
        "homework:homework",
    ]


@pytest.mark.asyncio
async def test_job_repository_tracks_durable_job_lifecycle():
    session = FakeJobSession()
    repository = SqlAlchemyNotificationJobRepository(session, tenant_id=1)

    queued = await repository.create_job(
        NotificationJobDraft(job_type="materialize_active_rules", scope={"shadow": True})
    )
    running = await repository.mark_running(queued.job_id)
    succeeded = await repository.mark_succeeded(
        queued.job_id,
        result_summary={"planned_count": 2},
    )

    job = session.objects[queued.job_id]
    assert queued.status == "queued"
    assert running.status == "running"
    assert succeeded.status == "succeeded"
    assert job.result_summary == {"planned_count": 2}
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_job_repository_claims_queued_jobs_with_processing_lock():
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    job = SimpleNamespace(
        id=1,
        tenant_id=1,
        job_type="materialize_active_rules",
        status="queued",
        scope={"shadow": True},
        started_at=None,
        finished_at=None,
        result_summary=None,
        error=None,
        updated_at=now,
    )
    session = FakeQueuedJobSession([job])
    repository = SqlAlchemyNotificationJobRepository(
        session,
        tenant_id=1,
        now_factory=lambda: now + timedelta(minutes=1),
    )

    result = await repository.claim_queued_jobs(job_type="materialize_active_rules", limit=10)

    assert len(result) == 1
    assert result[0].status == "running"
    assert job.status == "running"
    assert job.started_at == now + timedelta(minutes=1)
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_audit_log_repository_records_actor_and_entity_snapshot():
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    session = FakeJobSession()
    repository = SqlAlchemyNotificationAuditLogRepository(
        session,
        tenant_id=1,
        now_factory=lambda: now,
    )

    result = await repository.record_audit(
        NotificationAuditLogDraft(
            actor_type="teacher",
            actor_id=42,
            entity_type="notification_rule",
            entity_id=7,
            action="updated",
            before={"status": "draft"},
            after={"status": "active"},
            reason="manual",
            metadata={"source": "test"},
        )
    )

    audit = session.objects[result.audit_id]
    assert isinstance(audit, NotificationAuditLog)
    assert audit.tenant_id == 1
    assert audit.actor_id == 42
    assert audit.entity_type == "notification_rule"
    assert audit.after == {"status": "active"}
    assert result.metadata == {"source": "test"}
    assert result.created_at == now


def test_queued_jobs_claim_statement_uses_postgresql_skip_locked():
    stmt = _queued_jobs_for_claim_stmt(
        tenant_id=1,
        job_type="materialize_active_rules",
        limit=20,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_due_instances_claim_statement_skips_answered_instances():
    stmt = _due_instances_for_claim_stmt(
        tenant_id=1,
        now=datetime(2026, 4, 21, 18, 30, tzinfo=timezone.utc),
        limit=10,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_instances.status = " in compiled
    assert "notification_instances.delivery_enabled IS true" in compiled
    assert "notification_responses.notification_instance_id = notification_instances.id" in compiled


@pytest.mark.asyncio
async def test_instance_repository_can_cancel_future_instances_for_rules():
    session = FakeBulkUpdateSession()
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    result = await repository.cancel_future_instances_for_rules(
        rule_ids=(1, 2, 1),
        reason="rematerialized:active_rules",
    )

    assert result == 3
    compiled = str(session.calls[0][0].compile(dialect=postgresql.dialect()))
    assert "UPDATE notification_instances" in compiled
    assert "status" in compiled


def test_due_instances_claim_statement_uses_postgresql_skip_locked():
    stmt = _due_instances_for_claim_stmt(
        tenant_id=1,
        now=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        limit=100,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in compiled
    assert "notification_instances.status = %(status_1)s" in compiled
    assert "notification_instances.delivery_enabled IS true" in compiled
    assert "LEFT OUTER JOIN" not in compiled


def test_event_lookup_statements_are_scoped_to_tenant_and_event_id():
    lesson_stmt = _lesson_event_by_id_stmt(tenant_id=1, event_id=617)
    package_stmt = _package_event_by_id_stmt(tenant_id=1, event_id=64)

    compiled_lesson = str(lesson_stmt.compile(dialect=postgresql.dialect()))
    compiled_package = str(package_stmt.compile(dialect=postgresql.dialect()))

    assert "lessons.tenant_id =" in compiled_lesson
    assert "lessons.id =" in compiled_lesson
    assert "JOIN lesson_packages" in compiled_lesson
    assert "lesson_packages.tenant_id =" in compiled_package
    assert "lesson_packages.id =" in compiled_package
    assert "lesson_packages.end_date IS NOT NULL" in compiled_package


def test_notification_instances_statement_supports_queue_filters():
    stmt = _notification_instances_stmt(
        tenant_id=1,
        statuses=("scheduled", "shadow"),
        learner_id=10,
        event_type=EventType.LESSON,
        scheduled_from=datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc),
        scheduled_to=datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc),
        limit=50,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_instances.tenant_id =" in compiled
    assert "notification_instances.status IN" in compiled
    assert "notification_instances.learner_id =" in compiled
    assert "notification_instances.event_type =" in compiled
    assert "notification_instances.effective_scheduled_for >=" in compiled
    assert "notification_instances.effective_scheduled_for <" in compiled
    assert "LEFT OUTER JOIN learners" in compiled


def test_activity_statements_filter_by_tenant_and_learner():
    delivery_stmt = _delivery_activity_stmt(tenant_id=1, learner_id=10, limit=20)
    response_stmt = _response_activity_stmt(tenant_id=1, learner_id=10, limit=20)

    compiled_delivery = str(delivery_stmt.compile(dialect=postgresql.dialect()))
    compiled_response = str(response_stmt.compile(dialect=postgresql.dialect()))

    assert "notification_delivery_attempts.tenant_id =" in compiled_delivery
    assert "notification_instances.learner_id =" in compiled_delivery
    assert "coalesce(" in compiled_delivery
    assert "notification_responses.tenant_id =" in compiled_response
    assert "notification_responses.learner_id =" in compiled_response


def test_audit_log_statement_filters_by_tenant_and_entity():
    stmt = _notification_audit_log_stmt(
        tenant_id=1,
        entity_type="notification_rule",
        entity_id=7,
        limit=20,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_audit_log.tenant_id =" in compiled
    assert "notification_audit_log.entity_type =" in compiled
    assert "notification_audit_log.entity_id =" in compiled
    assert "ORDER BY notification_audit_log.created_at DESC" in compiled


def test_instance_and_activity_mappers_preserve_ui_context():
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    category = NotificationCategory(key="lesson_confirmation", display_name="Подтверждение")
    instance = NotificationInstance(
        id=16016,
        tenant_id=1,
        rule_id=16017,
        category=category,
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="scheduled",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        explanation={"rule_name": "Подтверждение"},
        created_at=now,
        updated_at=now,
    )
    instance.components = [
        NotificationInstanceComponent(
            id=501,
            rule_id=16017,
            category=category,
            template_id=3,
            component_key="lesson_confirmation:default",
            component_metadata={"source": "rule"},
        )
    ]
    instance.attempts = [
        NotificationDeliveryAttempt(
            id=201,
            tenant_id=1,
            notification_instance_id=16016,
            attempt_no=1,
            status="sent",
            channel="telegram",
            provider="telegram",
            provider_message_id="777",
            started_at=now,
            sent_at=now + timedelta(seconds=3),
            finished_at=now + timedelta(seconds=3),
            created_at=now,
        )
    ]

    instance_record = _instance_record_from_row(FakeRow(instance, learner_display_name="Вика"))
    delivery_activity = _delivery_activity_from_row(
        FakeRow(
            instance.attempts[0],
            instance_id=16016,
            category_key="lesson_confirmation",
            event_type="lesson",
            event_id=617,
            learner_id=10,
            learner_display_name="Вика",
            occurred_at=now + timedelta(seconds=3),
        )
    )
    response_activity = _response_activity_from_row(
        FakeRow(
            NotificationResponse(
                id=301,
                tenant_id=1,
                notification_instance_id=16016,
                event_type="lesson",
                event_id=617,
                recipient_type="learner",
                recipient_id=10,
                learner_id=10,
                action_key="confirm_lesson",
                response_value="confirmed",
                response_metadata={"source": "callback"},
                created_at=now + timedelta(seconds=10),
            ),
            instance_id=16016,
            category_key="lesson_confirmation",
            event_type="lesson",
            event_id=617,
            learner_id=10,
            learner_display_name="Вика",
            occurred_at=now + timedelta(seconds=10),
        )
    )
    teacher_alert_activity = _response_activity_from_row(
        FakeRow(
            NotificationResponse(
                id=302,
                tenant_id=1,
                notification_instance_id=16016,
                event_type="lesson",
                event_id=617,
                recipient_type="learner",
                recipient_id=10,
                learner_id=10,
                action_key="decline_lesson",
                response_value="declined",
                response_text="Не успеваю сегодня",
                response_metadata={"source": "callback"},
                created_at=now + timedelta(seconds=20),
            ),
            instance_id=16016,
            category_key="lesson_confirmation",
            event_type="lesson",
            event_id=617,
            learner_id=10,
            learner_display_name="Вика",
            occurred_at=now + timedelta(seconds=20),
        )
    )
    package_discussion_activity = _response_activity_from_row(
        FakeRow(
            NotificationResponse(
                id=303,
                tenant_id=1,
                notification_instance_id=17017,
                event_type="package",
                event_id=64,
                recipient_type="learner",
                recipient_id=10,
                learner_id=10,
                action_key="discuss_package_renewal",
                response_value="needs_discussion",
                response_metadata={"source": "callback"},
                created_at=now + timedelta(seconds=30),
            ),
            instance_id=17017,
            category_key="package_renewal",
            event_type="package",
            event_id=64,
            learner_id=10,
            learner_display_name="Вика",
            occurred_at=now + timedelta(seconds=30),
        )
    )

    assert instance_record.instance_id == 16016
    assert instance_record.learner_display_name == "Вика"
    assert instance_record.components[0].component_key == "lesson_confirmation:default"
    assert instance_record.latest_attempt is not None
    assert instance_record.latest_attempt.provider_message_id == "777"
    assert delivery_activity.activity_type == "delivery_attempt"
    assert delivery_activity.provider_message_id == "777"
    assert response_activity.activity_type == "response"
    assert response_activity.action_key == "confirm_lesson"
    assert teacher_alert_activity.activity_type == "teacher_alert"
    assert teacher_alert_activity.category == CategoryKey.TEACHER_ALERT
    assert teacher_alert_activity.status == "requires_attention"
    assert teacher_alert_activity.metadata["response_text"] == "Не успеваю сегодня"
    assert teacher_alert_activity.metadata["alert_code"] == "lesson_declined"
    assert package_discussion_activity.activity_type == "teacher_alert"
    assert package_discussion_activity.category == CategoryKey.TEACHER_ALERT
    assert package_discussion_activity.status == "requires_attention"
    assert package_discussion_activity.response_value == "needs_discussion"
    assert package_discussion_activity.metadata["alert_code"] == "package_renewal_needs_discussion"


@pytest.mark.asyncio
async def test_instance_repository_cancels_scheduled_instance():
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=16016,
        tenant_id=1,
        rule_id=16017,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="scheduled",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        explanation={},
        created_at=now,
        updated_at=now,
    )
    instance.components = []
    instance.attempts = []
    session = FakeInstanceActionSession(instance)
    repository = SqlAlchemyNotificationInstanceRepository(
        session,
        tenant_id=1,
        now_factory=lambda: now + timedelta(minutes=1),
    )

    result = await repository.cancel_instance(16016, reason="teacher_cancelled")

    assert result is not None
    assert result.status == InstanceStatus.CANCELLED
    assert instance.status == "cancelled"
    assert instance.status_reason == "teacher_cancelled"
    assert instance.delivery_enabled is False
    assert instance.updated_at == now + timedelta(minutes=1)
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_instance_repository_schedules_instance_now_for_delivery_pipeline():
    original = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    send_now = datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=16016,
        tenant_id=1,
        rule_id=16017,
        category=NotificationCategory(key="homework", display_name="Домашка"),
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=original,
        effective_scheduled_for=original,
        status="failed",
        delivery_enabled=False,
        priority="normal",
        channel="telegram",
        dedupe_key="single|homework|x",
        explanation={},
        created_at=original,
        updated_at=original,
    )
    instance.components = []
    instance.attempts = []
    session = FakeInstanceActionSession(instance)
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    result = await repository.schedule_instance_now(16016, now=send_now)

    assert result is not None
    assert result.status == InstanceStatus.SCHEDULED
    assert instance.status == "scheduled"
    assert instance.status_reason == "manual_send_now"
    assert instance.effective_scheduled_for == send_now
    assert instance.scheduled_for == original
    assert instance.delivery_enabled is True
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_instance_repository_cancels_future_instances_for_event():
    session = FakeBulkUpdateSession()
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    cancelled = await repository.cancel_future_instances_for_event(
        event_type=EventType.LESSON,
        event_id=617,
        reason="reconciled:lesson_updated",
    )

    compiled = str(session.calls[0][0].compile(dialect=postgresql.dialect()))
    assert cancelled == 3
    assert "UPDATE notification_instances" in compiled
    assert "notification_instances.event_type =" in compiled
    assert "notification_instances.event_id =" in compiled
    assert "notification_instances.status IN" in compiled


@pytest.mark.asyncio
async def test_instance_repository_cancels_future_instances_for_group_rule_scope():
    session = FakeBulkUpdateSession()
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    cancelled = await repository.cancel_future_instances_for_rules_and_learners(
        rule_ids=(1, 2),
        learner_ids=(10, 11),
        reason="reconciled:group_members_added",
    )

    compiled = str(session.calls[0][0].compile(dialect=postgresql.dialect()))
    assert cancelled == 3
    assert "UPDATE notification_instances" in compiled
    assert "notification_instances.learner_id IN" in compiled
    assert "notification_instances.rule_id IN" in compiled
    assert "notification_instance_components" in compiled
    assert "notification_instances.status IN" in compiled


@pytest.mark.asyncio
async def test_instance_repository_rejects_send_now_for_shadow_instance():
    now = datetime(2026, 4, 8, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=16016,
        tenant_id=1,
        category=NotificationCategory(key="homework", display_name="Домашка"),
        event_type="lesson",
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="shadow",
        delivery_enabled=False,
        priority="normal",
        channel="telegram",
        dedupe_key="single|homework|x",
    )
    session = FakeInstanceActionSession(instance)
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    with pytest.raises(ValueError, match="shadow"):
        await repository.schedule_instance_now(16016, now=now)


@pytest.mark.asyncio
async def test_instance_repository_claims_due_instances_and_creates_processing_attempt():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        rule_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="scheduled",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        explanation={"rule_name": "Подтверждение"},
    )
    session = FakeClaimSession([instance])
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    result = await repository.claim_due_instances(
        now=now,
        limit=100,
        lease_seconds=300,
        delivery_grace_seconds=120,
    )

    assert instance.status == "processing"
    assert instance.processing_started_at == now
    assert instance.processing_expires_at == now + timedelta(seconds=300)
    assert len(session.added) == 1
    attempt = session.added[0]
    assert isinstance(attempt, NotificationDeliveryAttempt)
    assert attempt.status == "processing"
    assert attempt.attempt_no == 1
    assert result.claimed[0].attempt_id == 201
    assert result.claimed[0].category == CategoryKey.LESSON_CONFIRMATION
    assert result.claimed[0].provider_chat_id == "5390064156"


@pytest.mark.asyncio
async def test_instance_repository_expires_stale_due_instances_before_claiming():
    now = datetime(2026, 4, 7, 7, 5, tzinfo=timezone.utc)
    stale_instance = NotificationInstance(
        id=101,
        tenant_id=1,
        rule_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now - timedelta(minutes=5),
        effective_scheduled_for=now - timedelta(minutes=5),
        status="scheduled",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        explanation={"rule_name": "Подтверждение"},
    )
    session = FakeClaimSession([], stale_instances=(stale_instance,))
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    result = await repository.claim_due_instances(
        now=now,
        limit=100,
        lease_seconds=300,
        delivery_grace_seconds=120,
    )

    assert result.claimed == ()
    assert stale_instance.status == "expired"
    assert stale_instance.status_reason == "delivery_window_exceeded"
    assert stale_instance.delivery_enabled is False


@pytest.mark.asyncio
async def test_instance_repository_marks_delivery_attempt_sent():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="processing",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        processing_started_at=now,
        processing_expires_at=now + timedelta(minutes=5),
    )
    attempt = NotificationDeliveryAttempt(
        id=201,
        tenant_id=1,
        notification_instance_id=101,
        attempt_no=1,
        status="processing",
        channel="telegram",
        provider="telegram",
        started_at=now,
    )
    session = FakeDeliverySession(instance, attempt)
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    await repository.mark_delivery_sent(
        instance_id=101,
        attempt_id=201,
        rendered=RenderedNotification(
            text="Привет, Вика!",
            reply_markup_snapshot={"inline_keyboard": []},
        ),
        send_result=DeliverySendResult(
            provider="telegram",
            provider_chat_id="5390064156",
            provider_message_id="777",
            sent_at=now + timedelta(seconds=5),
        ),
    )

    assert instance.status == "sent"
    assert instance.delivery_enabled is False
    assert instance.processing_started_at is None
    assert instance.processing_expires_at is None
    assert attempt.status == "sent"
    assert attempt.provider_message_id == "777"
    assert attempt.rendered_text == "Привет, Вика!"
    assert attempt.reply_markup_snapshot == {"inline_keyboard": []}
    assert attempt.finished_at == now + timedelta(seconds=5)
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_instance_repository_marks_retryable_delivery_failure_as_scheduled():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="processing",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        processing_started_at=now,
        processing_expires_at=now + timedelta(minutes=5),
    )
    attempt = NotificationDeliveryAttempt(
        id=201,
        tenant_id=1,
        notification_instance_id=101,
        attempt_no=1,
        status="processing",
        channel="telegram",
        provider="telegram",
        started_at=now,
    )
    session = FakeDeliverySession(instance, attempt)
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    await repository.mark_delivery_failed(
        instance_id=101,
        attempt_id=201,
        error_code="telegram_timeout",
        error_message="Telegram timeout",
        retryable=True,
        failed_at=now + timedelta(seconds=5),
    )

    assert instance.status == "scheduled"
    assert instance.delivery_enabled is True
    assert instance.status_reason == "telegram_timeout"
    assert instance.processing_started_at is None
    assert instance.processing_expires_at is None
    assert attempt.status == "failed_retryable"
    assert attempt.error_code == "telegram_timeout"
    assert attempt.finished_at == now + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_instance_repository_marks_permanent_delivery_failure_as_failed():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="processing",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
    )
    attempt = NotificationDeliveryAttempt(
        id=201,
        tenant_id=1,
        notification_instance_id=101,
        attempt_no=1,
        status="processing",
        channel="telegram",
        provider="telegram",
        started_at=now,
    )
    session = FakeDeliverySession(instance, attempt)
    repository = SqlAlchemyNotificationInstanceRepository(session, tenant_id=1)

    await repository.mark_delivery_failed(
        instance_id=101,
        attempt_id=201,
        error_code="telegram_forbidden",
        error_message="Bot was blocked by the user",
        retryable=False,
        failed_at=now + timedelta(seconds=5),
    )

    assert instance.status == "failed"
    assert instance.delivery_enabled is False
    assert instance.status_reason == "telegram_forbidden"
    assert attempt.status == "failed"


@pytest.mark.asyncio
async def test_response_repository_records_lesson_response_and_upserts_participant_state():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        category=NotificationCategory(key="lesson_confirmation", display_name="Подтверждение"),
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="sent",
        delivery_enabled=False,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
    )
    session = FakeResponseSession(instance)
    repository = SqlAlchemyNotificationResponseRepository(
        session,
        tenant_id=1,
        now_factory=lambda: now,
    )

    result = await repository.record_response(
        NotificationResponseDraft(
            notification_instance_id=101,
            action_key="confirm_lesson",
            response_value="confirmed",
        )
    )

    assert result.response_id == 301
    assert result.response_value == "confirmed"
    assert result.lesson_participant_state_updated is True
    assert isinstance(session.added[0], NotificationResponse)
    assert session.added[0].event_type == "lesson"
    assert session.added[0].event_id == 617
    assert session.added[0].learner_id == 10
    compiled = str(session.executed[0][0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_lesson_participant_state_lesson_learner" in compiled


@pytest.mark.asyncio
async def test_response_repository_records_non_lesson_response_without_participant_state():
    now = datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    instance = NotificationInstance(
        id=101,
        tenant_id=1,
        category=NotificationCategory(key="package_renewal", display_name="Продление"),
        event_type="package",
        event_id=64,
        event_key="package:64",
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        scheduled_for=now,
        effective_scheduled_for=now,
        status="sent",
        delivery_enabled=False,
        priority="normal",
        channel="telegram",
        dedupe_key="single|package_renewal|x",
    )
    session = FakeResponseSession(instance)
    repository = SqlAlchemyNotificationResponseRepository(
        session,
        tenant_id=1,
        now_factory=lambda: now,
    )

    result = await repository.record_response(
        NotificationResponseDraft(
            notification_instance_id=101,
            action_key="confirm_package_renewal",
            response_value="confirmed",
        )
    )

    assert result.lesson_participant_state_updated is False
    assert session.executed == []
