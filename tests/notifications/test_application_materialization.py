from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from notifications.application.dto import (
    AudienceSelector,
    ClaimDueNotificationsResult,
    ClaimedNotificationInstance,
    DeliverySendResult,
    ExecuteNotificationDeliveryResult,
    InstanceUpsertResult,
    LearnerNotificationModeRecord,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationSettingsRecord,
    NotificationInstanceDraft,
    NotificationRuleDraft,
    PreviewEvent,
    PreviewRecipient,
    RenderedNotification,
)
from notifications.application.delivery import (
    ClaimDueNotificationsUseCase,
    ExecuteClaimedNotificationDeliveryUseCase,
    NotificationDeliveryError,
)
from notifications.application.materialization import (
    MaterializeActiveRulesUseCase,
    MaterializeRulesUseCase,
    RunMaterializeActiveRulesJobUseCase,
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
    events: tuple[PreviewEvent, ...]

    async def list_events_for_recipients(self, *, event_type, learner_ids, horizon_days, limit, offset=0):
        events = tuple(
            event
            for event in self.events
            if event.event_type == event_type and event.learner_id in learner_ids
        )
        return events[offset:offset + limit]


class FakePreferenceRepository:
    async def get_global_preference(self):
        return None

    async def get_group_preferences_for_learner(self, learner_id):
        return ()

    async def get_learner_preference(self, learner_id):
        return None


@dataclass
class FakeSettingsRepository:
    settings: NotificationSettingsRecord = field(
        default_factory=lambda: NotificationSettingsRecord(
            tenant_id=1,
            mode=NotificationSystemMode.LEGACY,
        )
    )
    learner_modes: tuple[LearnerNotificationModeRecord, ...] = ()

    async def get_settings(self):
        return self.settings

    async def list_learner_modes(self):
        return self.learner_modes

    async def clear_learner_modes(self):
        self.learner_modes = ()


@dataclass
class FakeInstanceRepository:
    upserted: tuple[NotificationInstanceDraft, ...] = ()
    claim_result: ClaimDueNotificationsResult = ClaimDueNotificationsResult(claimed=())
    sent_calls: list[dict] = field(default_factory=list)
    failed_calls: list[dict] = field(default_factory=list)
    cancel_rule_calls: list[dict] = field(default_factory=list)
    claim_calls: list[dict] = field(default_factory=list)

    async def upsert_planned_instances(self, instances):
        self.upserted = instances
        return InstanceUpsertResult(planned_count=len(instances), inserted_count=len(instances))

    async def cancel_future_instances_for_rules(self, *, rule_ids, reason: str, statuses=None):
        self.cancel_rule_calls.append({"rule_ids": rule_ids, "reason": reason, "statuses": statuses})
        return 0

    async def claim_due_instances(self, *, now, limit: int, lease_seconds: int, delivery_grace_seconds: int = 0):
        self.claim_calls.append(
            {
                "now": now,
                "limit": limit,
                "lease_seconds": lease_seconds,
                "delivery_grace_seconds": delivery_grace_seconds,
            }
        )
        return self.claim_result

    async def mark_delivery_sent(self, **kwargs):
        self.sent_calls.append(kwargs)

    async def mark_delivery_failed(self, **kwargs):
        self.failed_calls.append(kwargs)


@dataclass
class FakeRuleRepository:
    rules: tuple[NotificationRuleDraft, ...]

    async def list_active_rules(self):
        return self.rules

    async def list_rules(self, *, include_archived=False):
        return self.rules


@dataclass
class FakeJobRepository:
    records: list[NotificationJobRecord] = field(default_factory=list)
    summaries: list[dict] = field(default_factory=list)

    async def create_job(self, draft: NotificationJobDraft):
        record = NotificationJobRecord(
            job_id=1,
            job_type=draft.job_type,
            status="queued",
            scope=draft.scope,
        )
        self.records.append(record)
        return record

    async def mark_running(self, job_id: int):
        record = NotificationJobRecord(
            job_id=job_id,
            job_type=self.records[-1].job_type,
            status="running",
            scope=self.records[-1].scope,
        )
        self.records.append(record)
        return record

    async def mark_succeeded(self, job_id: int, *, result_summary: dict):
        self.summaries.append(result_summary)
        record = NotificationJobRecord(
            job_id=job_id,
            job_type=self.records[-1].job_type,
            status="succeeded",
            scope=self.records[-1].scope,
        )
        self.records.append(record)
        return record

    async def mark_failed(self, job_id: int, *, error: str):
        raise AssertionError("mark_failed should not be called in this test")


@dataclass
class FakeMaterializationUnitOfWork:
    audience_resolver: FakeAudienceResolver
    events: FakeEventRepository
    preferences: FakePreferenceRepository = field(default_factory=FakePreferenceRepository)
    settings: FakeSettingsRepository = field(default_factory=FakeSettingsRepository)
    rules: FakeRuleRepository = field(default_factory=lambda: FakeRuleRepository(rules=()))
    jobs: FakeJobRepository = field(default_factory=FakeJobRepository)
    instances: FakeInstanceRepository = field(default_factory=FakeInstanceRepository)
    committed: bool = False

    async def commit(self):
        self.committed = True


@dataclass
class FakeRenderer:
    rendered: RenderedNotification = field(
        default_factory=lambda: RenderedNotification(
            text="Привет, Вика!",
            parse_mode=None,
            reply_markup_snapshot={"inline_keyboard": []},
        )
    )

    async def render(self, instance):
        return self.rendered


@dataclass
class FakeChannelAdapter:
    result: DeliverySendResult | None = None
    error: Exception | None = None

    async def send(self, *, instance, rendered):
        if self.error is not None:
            raise self.error
        return self.result or DeliverySendResult(
            provider="telegram",
            provider_chat_id="5390064156",
            provider_message_id="777",
            sent_at=datetime(2026, 4, 7, 7, 0, 5, tzinfo=timezone.utc),
        )


def _draft(
    category: CategoryKey = CategoryKey.LESSON_CONFIRMATION,
    *,
    rule_id: int = 1,
) -> NotificationRuleDraft:
    return NotificationRuleDraft(
        rule_id=rule_id,
        name=category.value,
        category=category,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Привет, {student_name}!",
        template_key=category.value,
        assignments=(AudienceSelector(scope_type="learner", scope_id=10),),
    )


def _claimed_instance() -> ClaimedNotificationInstance:
    return ClaimedNotificationInstance(
        instance_id=101,
        attempt_id=201,
        attempt_no=1,
        rule_id=1,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        priority=Priority.NORMAL,
        channel="telegram",
    )


def _uow(
    *,
    recipient: PreviewRecipient | None = None,
    event: PreviewEvent | None = None,
) -> FakeMaterializationUnitOfWork:
    future_start = datetime.now(timezone.utc) + timedelta(days=14)
    return FakeMaterializationUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(recipient or PreviewRecipient(learner_id=10, display_name="Вика"),)
        ),
        events=FakeEventRepository(
            events=(
                event
                or PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=617,
                    learner_id=10,
                    starts_at=future_start,
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
            )
        ),
    )


@pytest.mark.asyncio
async def test_materialize_rules_upserts_scheduled_instance_drafts():
    uow = _uow()

    result = await MaterializeRulesUseCase(uow).execute((_draft(),))

    assert uow.committed
    assert result.upsert_result.inserted_count == 1
    instance = result.planned_instances[0]
    assert instance.status == InstanceStatus.SCHEDULED
    assert instance.delivery_enabled is True
    assert instance.dedupe_key.startswith("single|lesson_confirmation|lesson_confirmation|")
    assert uow.instances.upserted == result.planned_instances


@pytest.mark.asyncio
async def test_materialize_rules_pages_through_all_matching_events():
    future_start = datetime.now(timezone.utc) + timedelta(days=14)
    uow = FakeMaterializationUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(PreviewRecipient(learner_id=10, display_name="Вика"),)
        ),
        events=FakeEventRepository(
            events=(
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=617,
                    learner_id=10,
                    starts_at=future_start,
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=618,
                    learner_id=10,
                    starts_at=future_start + timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=619,
                    learner_id=10,
                    starts_at=future_start + timedelta(days=2),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
            )
        ),
    )

    result = await MaterializeRulesUseCase(uow).execute((_draft(),), limit=1)

    assert result.upsert_result.planned_count == 3
    assert len(result.planned_instances) == 3
    assert [instance.event_id for instance in result.planned_instances] == [617, 618, 619]
    assert len(uow.instances.upserted) == 3


@pytest.mark.asyncio
async def test_materialize_rules_can_create_shadow_instances_without_delivery():
    result = await MaterializeRulesUseCase(_uow()).execute((_draft(),), shadow=True)

    instance = result.planned_instances[0]
    assert instance.status == InstanceStatus.SHADOW
    assert instance.delivery_enabled is False


@pytest.mark.asyncio
async def test_materialize_rules_keeps_skipped_no_contact_instance_visible():
    recipient = PreviewRecipient(learner_id=10, display_name="Вика", has_contact=False)

    result = await MaterializeRulesUseCase(_uow(recipient=recipient)).execute((_draft(),))

    instance = result.planned_instances[0]
    assert instance.status == InstanceStatus.SKIPPED
    assert instance.status_reason == "missing_contact"
    assert instance.delivery_enabled is False


@pytest.mark.asyncio
async def test_materialize_rules_creates_combined_instance_with_components():
    confirmation = _draft(CategoryKey.LESSON_CONFIRMATION, rule_id=1)
    homework = _draft(CategoryKey.HOMEWORK, rule_id=2)
    event = PreviewEvent(
        event_type=EventType.LESSON,
        event_id=617,
        learner_id=10,
        starts_at=datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc),
        timezone="UTC",
        package_status="active",
        lesson_status="scheduled",
        has_homework=True,
        metadata={
            "calendar_conflict_count": 2,
            "calendar_conflict_lesson_ids": [581, 617],
            "calendar_conflict_package_ids": [64, 74],
        },
    )

    result = await MaterializeRulesUseCase(_uow(event=event)).execute((confirmation, homework))

    assert len(result.planned_instances) == 1
    instance = result.planned_instances[0]
    assert instance.rule_id is None
    assert instance.combination_key == "lesson_confirmation_homework"
    assert instance.dedupe_key.startswith("combined|lesson_confirmation_homework|")
    assert "calendar_conflict:active_lessons_same_slot" in instance.explanation["warnings"]
    assert instance.explanation["component_explanations"][0]["calendar_conflict"]["count"] == 2
    assert [component.category for component in instance.components] == [
        CategoryKey.LESSON_CONFIRMATION,
        CategoryKey.HOMEWORK,
    ]


@pytest.mark.asyncio
async def test_materialize_rules_keeps_single_instance_warnings_and_event_context():
    event = PreviewEvent(
        event_type=EventType.LESSON,
        event_id=617,
        learner_id=10,
        starts_at=datetime(2026, 4, 8, 20, 0, tzinfo=timezone.utc),
        timezone="UTC",
        package_status="active",
        lesson_status="scheduled",
        has_homework=True,
        metadata={
            "calendar_conflict_count": 2,
            "calendar_conflict_lesson_ids": [581, 617],
            "calendar_conflict_package_ids": [64, 74],
        },
    )

    result = await MaterializeRulesUseCase(_uow(event=event)).execute((_draft(),))

    instance = result.planned_instances[0]
    assert instance.explanation["warnings"] == ["calendar_conflict:active_lessons_same_slot"]
    assert instance.explanation["event_starts_at"] == "2026-04-08T20:00:00+00:00"
    assert instance.explanation["calendar_conflict"]["count"] == 2


@pytest.mark.asyncio
async def test_materialize_active_rules_records_job_summary():
    rule = _draft()
    uow = _uow()
    uow.rules = FakeRuleRepository(rules=(rule,))
    uow.settings = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW),
        learner_modes=(
            LearnerNotificationModeRecord(
                learner_id=10,
                display_name="Вика",
                mode_override=NotificationSystemMode.INHERIT,
                effective_mode=NotificationSystemMode.SHADOW,
            ),
        ),
    )

    result = await MaterializeActiveRulesUseCase(uow).execute()

    assert uow.committed
    assert result.job.status == "succeeded"
    assert uow.jobs.summaries == [
        {
            "rules_count": 1,
            "cancelled_count": 0,
            "planned_count": 1,
            "upserted_count": 0,
            "warnings": [],
        }
    ]
    assert uow.instances.cancel_rule_calls == [
        {"rule_ids": (1,), "reason": "rematerialized:all_rules", "statuses": None}
    ]


@pytest.mark.asyncio
async def test_materialize_active_rules_shadow_rebuild_does_not_enable_rollout_delivery():
    future_start = datetime.now(timezone.utc) + timedelta(days=14)
    rule = NotificationRuleDraft(
        rule_id=1,
        name="lesson_confirmation",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation",
        assignments=(AudienceSelector(scope_type="all_learners", scope_id=None),),
    )
    uow = FakeMaterializationUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(
                PreviewRecipient(learner_id=10, display_name="Вика"),
                PreviewRecipient(learner_id=11, display_name="Ира"),
            )
        ),
        events=FakeEventRepository(
            events=(
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=617,
                    learner_id=10,
                    starts_at=future_start,
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=618,
                    learner_id=11,
                    starts_at=future_start + timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
            )
        ),
        settings=FakeSettingsRepository(
            settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
            learner_modes=(
                LearnerNotificationModeRecord(
                    learner_id=10,
                    display_name="Вика",
                    mode_override=NotificationSystemMode.NEW,
                    effective_mode=NotificationSystemMode.NEW,
                ),
                LearnerNotificationModeRecord(
                    learner_id=11,
                    display_name="Ира",
                    mode_override=NotificationSystemMode.INHERIT,
                    effective_mode=NotificationSystemMode.LEGACY,
                ),
            ),
        ),
        rules=FakeRuleRepository(rules=(rule,)),
    )

    result = await MaterializeActiveRulesUseCase(uow).execute(
        delivery_enabled=False,
        shadow=True,
    )

    assert len(result.materialization.planned_instances) == 2
    assert {instance.learner_id for instance in result.materialization.planned_instances} == {10, 11}
    assert {
        instance.status for instance in result.materialization.planned_instances
    } == {InstanceStatus.SHADOW}
    assert {
        instance.delivery_enabled for instance in result.materialization.planned_instances
    } == {False}
    assert uow.instances.cancel_rule_calls == [
        {
            "rule_ids": (1,),
            "reason": "rematerialized:shadow_all_rules",
            "statuses": (InstanceStatus.SHADOW,),
        }
    ]


@pytest.mark.asyncio
async def test_materialize_active_rules_live_run_respects_learner_rollout_modes():
    future_start = datetime.now(timezone.utc) + timedelta(days=14)
    rule = NotificationRuleDraft(
        rule_id=1,
        name="lesson_confirmation",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation",
        assignments=(AudienceSelector(scope_type="all_learners", scope_id=None),),
    )
    uow = FakeMaterializationUnitOfWork(
        audience_resolver=FakeAudienceResolver(
            recipients=(
                PreviewRecipient(learner_id=10, display_name="Вика"),
                PreviewRecipient(learner_id=11, display_name="Ира"),
            )
        ),
        events=FakeEventRepository(
            events=(
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=617,
                    learner_id=10,
                    starts_at=future_start,
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=618,
                    learner_id=11,
                    starts_at=future_start + timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
            )
        ),
        settings=FakeSettingsRepository(
            settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
            learner_modes=(
                LearnerNotificationModeRecord(
                    learner_id=10,
                    display_name="Вика",
                    mode_override=NotificationSystemMode.NEW,
                    effective_mode=NotificationSystemMode.NEW,
                ),
                LearnerNotificationModeRecord(
                    learner_id=11,
                    display_name="Ира",
                    mode_override=NotificationSystemMode.INHERIT,
                    effective_mode=NotificationSystemMode.LEGACY,
                ),
            ),
        ),
        rules=FakeRuleRepository(rules=(rule,)),
    )

    result = await MaterializeActiveRulesUseCase(uow).execute()

    assert len(result.materialization.planned_instances) == 1
    instance = result.materialization.planned_instances[0]
    assert instance.learner_id == 10
    assert instance.status == InstanceStatus.SCHEDULED
    assert instance.delivery_enabled is True


@pytest.mark.asyncio
async def test_materialize_active_rules_cleans_future_instances_for_paused_rules():
    active_rule = _draft(rule_id=5)

    @dataclass
    class FakeRuleCatalogRepository(FakeRuleRepository):
        all_rules: tuple[NotificationRuleDraft, ...] = ()

        async def list_rules(self, *, include_archived=False):
            return self.all_rules if include_archived else self.rules

    uow = _uow()
    uow.rules = FakeRuleCatalogRepository(
        rules=(active_rule,),
        all_rules=(
            _draft(rule_id=1),
            _draft(rule_id=2),
            active_rule,
        ),
    )
    uow.settings = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
        learner_modes=(
            LearnerNotificationModeRecord(
                learner_id=10,
                display_name="Вика",
                mode_override=NotificationSystemMode.NEW,
                effective_mode=NotificationSystemMode.NEW,
            ),
        ),
    )

    await MaterializeActiveRulesUseCase(uow).execute()

    assert uow.instances.cancel_rule_calls == [
        {"rule_ids": (1, 2, 5), "reason": "rematerialized:all_rules", "statuses": None}
    ]


@pytest.mark.asyncio
async def test_materialize_active_rules_warns_when_live_candidates_are_past_due():
    soon_start = datetime.now(timezone.utc) + timedelta(minutes=30)
    uow = _uow(
        event=PreviewEvent(
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            starts_at=soon_start,
            timezone="UTC",
            package_status="active",
            lesson_status="scheduled",
            has_homework=True,
        )
    )
    uow.rules = FakeRuleRepository(rules=(_draft(),))

    result = await MaterializeActiveRulesUseCase(uow).execute()

    assert result.materialization.upsert_result.planned_count == 0
    assert result.materialization.warnings == ("past_due_instances_filtered:1",)
    assert uow.jobs.summaries[-1]["warnings"] == ["past_due_instances_filtered:1"]


@pytest.mark.asyncio
async def test_run_materialize_active_rules_job_uses_claimed_job_scope():
    rule = _draft()
    uow = _uow()
    uow.rules = FakeRuleRepository(rules=(rule,))
    uow.settings = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW),
        learner_modes=(
            LearnerNotificationModeRecord(
                learner_id=10,
                display_name="Вика",
                mode_override=NotificationSystemMode.INHERIT,
                effective_mode=NotificationSystemMode.SHADOW,
            ),
        ),
    )
    job = NotificationJobRecord(
        job_id=99,
        job_type="materialize_active_rules",
        status="running",
        scope={"horizon_days": 60, "limit": 200, "delivery_enabled": False, "shadow": True},
    )
    uow.jobs.records.append(job)

    result = await RunMaterializeActiveRulesJobUseCase(uow).execute(job)

    assert uow.committed
    assert result.job.status == "succeeded"
    assert result.materialization.planned_instances[0].status == InstanceStatus.SHADOW
    assert result.materialization.planned_instances[0].delivery_enabled is False
    assert uow.jobs.summaries[-1]["rules_count"] == 1
    assert uow.instances.cancel_rule_calls == [
        {
            "rule_ids": (1,),
            "reason": "rematerialized:shadow_all_rules",
            "statuses": (InstanceStatus.SHADOW,),
        }
    ]


@pytest.mark.asyncio
async def test_claim_due_notifications_commits_claimed_instances():
    uow = _uow()
    uow.instances.claim_result = ClaimDueNotificationsResult(
        claimed=(
            ClaimedNotificationInstance(
                instance_id=101,
                attempt_id=201,
                attempt_no=1,
                rule_id=1,
                category=CategoryKey.LESSON_CONFIRMATION,
                event_type=EventType.LESSON,
                event_id=617,
                recipient_type="learner",
                recipient_id=10,
                learner_id=10,
                effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
                priority=Priority.NORMAL,
                channel="telegram",
            ),
        )
    )

    result = await ClaimDueNotificationsUseCase(uow).execute(
        now=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        limit=100,
        delivery_grace_seconds=120,
    )

    assert uow.committed
    assert result.claimed[0].instance_id == 101
    assert uow.instances.claim_calls == [
        {
            "now": datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
            "limit": 100,
            "lease_seconds": 300,
            "delivery_grace_seconds": 120,
        }
    ]


@pytest.mark.asyncio
async def test_execute_claimed_notification_delivery_marks_attempt_sent():
    uow = _uow()
    renderer = FakeRenderer()
    adapter = FakeChannelAdapter()

    result = await ExecuteClaimedNotificationDeliveryUseCase(
        uow,
        renderer=renderer,
        channel_adapter=adapter,
    ).execute(_claimed_instance())

    assert isinstance(result, ExecuteNotificationDeliveryResult)
    assert uow.committed
    assert result.status == InstanceStatus.SENT
    assert result.provider_message_id == "777"
    assert uow.instances.sent_calls == [
        {
            "instance_id": 101,
            "attempt_id": 201,
            "rendered": renderer.rendered,
            "send_result": adapter.result
            or DeliverySendResult(
                provider="telegram",
                provider_chat_id="5390064156",
                provider_message_id="777",
                sent_at=datetime(2026, 4, 7, 7, 0, 5, tzinfo=timezone.utc),
            ),
        }
    ]


@pytest.mark.asyncio
async def test_execute_claimed_notification_delivery_marks_retryable_failure():
    uow = _uow()
    error = NotificationDeliveryError(
        "Telegram timeout",
        error_code="telegram_timeout",
        retryable=True,
    )

    result = await ExecuteClaimedNotificationDeliveryUseCase(
        uow,
        renderer=FakeRenderer(),
        channel_adapter=FakeChannelAdapter(error=error),
    ).execute(_claimed_instance(), now=datetime(2026, 4, 7, 7, 1, tzinfo=timezone.utc))

    assert uow.committed
    assert result.status == InstanceStatus.SCHEDULED
    assert result.error_code == "telegram_timeout"
    assert uow.instances.failed_calls == [
        {
            "instance_id": 101,
            "attempt_id": 201,
            "error_code": "telegram_timeout",
            "error_message": "Telegram timeout",
            "retryable": True,
            "failed_at": datetime(2026, 4, 7, 7, 1, tzinfo=timezone.utc),
        }
    ]


@pytest.mark.asyncio
async def test_execute_claimed_notification_delivery_marks_permanent_failure():
    uow = _uow()
    error = NotificationDeliveryError(
        "Bot was blocked by the user",
        error_code="telegram_forbidden",
        retryable=False,
    )

    result = await ExecuteClaimedNotificationDeliveryUseCase(
        uow,
        renderer=FakeRenderer(),
        channel_adapter=FakeChannelAdapter(error=error),
    ).execute(_claimed_instance(), now=datetime(2026, 4, 7, 7, 1, tzinfo=timezone.utc))

    assert result.status == InstanceStatus.FAILED
    assert uow.instances.failed_calls[0]["retryable"] is False
