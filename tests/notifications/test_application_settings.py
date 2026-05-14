from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from notifications.application.dto import (
    AudienceSelector,
    InstanceUpsertResult,
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationInstanceDraft,
    NotificationRuleDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
    PreviewEvent,
    PreviewRecipient,
)
from notifications.application.settings import (
    GetLearnerNotificationModeUseCase,
    GetNotificationSettingsUseCase,
    ListLearnerNotificationModesUseCase,
    RebuildLearnerNotificationQueueUseCase,
    SetLearnerNotificationModeUseCase,
    UpdateNotificationSettingsUseCase,
)
from notifications.domain.enums import (
    CategoryKey,
    EventType,
    NotificationSystemMode,
    Priority,
    TriggerType,
)


@dataclass
class FakeSettingsRepository:
    settings: NotificationSettingsRecord
    learner_modes: tuple[LearnerNotificationModeRecord, ...] = ()
    updated_settings: NotificationSettingsUpdateDraft | None = None
    updated_learner_mode: tuple[int, LearnerNotificationModeUpdateDraft] | None = None
    cleared_learner_modes: bool = False

    async def get_settings(self):
        return self.settings

    async def update_settings(self, draft):
        mode = draft.mode or self.settings.mode
        self.updated_settings = draft
        self.settings = NotificationSettingsRecord(tenant_id=1, mode=mode)
        return self.settings

    async def clear_learner_modes(self):
        self.cleared_learner_modes = True
        self.learner_modes = ()

    async def list_learner_modes(self):
        return self.learner_modes

    async def get_learner_mode(self, learner_id):
        return next((mode for mode in self.learner_modes if mode.learner_id == learner_id), None)

    async def set_learner_mode(self, learner_id, draft):
        self.updated_learner_mode = (learner_id, draft)
        return LearnerNotificationModeRecord(
            learner_id=learner_id,
            display_name="Вика",
            mode_override=draft.mode_override,
            effective_mode=draft.mode_override,
        )


@dataclass
class FakeUnitOfWork:
    settings: FakeSettingsRepository
    rules: object = None
    instances: object = None
    audience_resolver: object = None
    events: object = None
    preferences: object = None
    jobs: object = None
    responses: object = None
    groups: object = None
    templates: object = None
    committed: bool = False

    def __post_init__(self):
        self.rules = self.rules or FakeRuleRepository()
        self.instances = self.instances or FakeInstanceRepository()
        self.audience_resolver = self.audience_resolver or FakeAudienceResolver()
        self.events = self.events or FakeEventRepository()
        self.preferences = self.preferences or FakePreferenceRepository()

    async def commit(self):
        self.committed = True


@dataclass
class FakeRuleRepository:
    rules: tuple[NotificationRuleDraft, ...] = ()

    async def list_active_rules(self):
        return self.rules

    async def list_rules(self, *, include_archived=False):
        return self.rules


@dataclass
class FakeInstanceRepository:
    upserted: tuple[NotificationInstanceDraft, ...] = ()
    cancel_scoped_calls: list[dict] = None

    def __post_init__(self):
        self.cancel_scoped_calls = self.cancel_scoped_calls or []

    async def cancel_future_instances_for_rules_and_learners(
        self,
        *,
        rule_ids,
        learner_ids,
        reason,
        statuses=None,
    ):
        self.cancel_scoped_calls.append(
            {"rule_ids": rule_ids, "learner_ids": learner_ids, "reason": reason, "statuses": statuses}
        )
        return 0

    async def cancel_future_instances_for_rules(self, *, rule_ids, reason, statuses=None):
        self.cancel_scoped_calls.append(
            {"rule_ids": rule_ids, "reason": reason, "statuses": statuses}
        )
        return 0

    async def upsert_planned_instances(self, instances):
        self.upserted = instances
        return InstanceUpsertResult(planned_count=len(instances), upserted_count=len(instances))


@dataclass
class FakeAudienceResolver:
    recipients: tuple[PreviewRecipient, ...] = ()

    async def resolve_recipients(self, assignments):
        return self.recipients


@dataclass
class FakeEventRepository:
    events: tuple[PreviewEvent, ...] = ()

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


@pytest.mark.asyncio
async def test_get_and_update_settings_use_cases():
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY)
    )
    uow = FakeUnitOfWork(settings=repository)
    draft = NotificationSettingsUpdateDraft(mode=NotificationSystemMode.SHADOW)

    current = await GetNotificationSettingsUseCase(uow).execute()
    updated = await UpdateNotificationSettingsUseCase(uow).execute(draft)

    assert current.mode == NotificationSystemMode.LEGACY
    assert updated.mode == NotificationSystemMode.SHADOW
    assert repository.updated_settings == draft
    assert uow.committed is True


@pytest.mark.asyncio
async def test_update_settings_requires_explicit_confirmation_for_global_new():
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW)
    )
    uow = FakeUnitOfWork(settings=repository)

    with pytest.raises(ValueError, match="requires explicit confirmation"):
        await UpdateNotificationSettingsUseCase(uow).execute(
            NotificationSettingsUpdateDraft(mode=NotificationSystemMode.NEW)
        )

    assert repository.updated_settings is None
    assert uow.committed is False


@pytest.mark.asyncio
async def test_update_settings_to_new_clears_overrides_and_rebuilds_future_queue():
    now = datetime.now(timezone.utc)
    rule = NotificationRuleDraft(
        rule_id=7,
        name="lesson_confirmation",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation",
        assignments=(AudienceSelector(scope_type="all_learners"),),
    )
    instances = FakeInstanceRepository()
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
        learner_modes=(
            LearnerNotificationModeRecord(
                learner_id=10,
                display_name="Вика",
                mode_override=NotificationSystemMode.SHADOW,
                effective_mode=NotificationSystemMode.SHADOW,
            ),
        ),
    )
    uow = FakeUnitOfWork(
        settings=repository,
        rules=FakeRuleRepository(rules=(rule,)),
        instances=instances,
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
                    starts_at=now + timedelta(days=7),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=False,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=618,
                    learner_id=11,
                    starts_at=now - timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=False,
                ),
            )
        ),
    )

    updated = await UpdateNotificationSettingsUseCase(uow).execute(
        NotificationSettingsUpdateDraft(
            mode=NotificationSystemMode.NEW,
            confirm_global_new=True,
        )
    )

    assert updated.mode == NotificationSystemMode.NEW
    assert repository.cleared_learner_modes is True
    assert instances.cancel_scoped_calls == [
        {"rule_ids": (7,), "reason": "rematerialized:all_rules", "statuses": None}
    ]
    assert len(instances.upserted) == 1
    assert instances.upserted[0].learner_id == 10
    assert instances.upserted[0].delivery_enabled is True
    assert uow.committed is True


@pytest.mark.asyncio
async def test_learner_mode_use_cases():
    mode = LearnerNotificationModeRecord(
        learner_id=10,
        display_name="Вика",
        mode_override=NotificationSystemMode.INHERIT,
        effective_mode=NotificationSystemMode.SHADOW,
    )
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW),
        learner_modes=(mode,),
    )
    uow = FakeUnitOfWork(settings=repository)

    listed = await ListLearnerNotificationModesUseCase(uow).execute()
    fetched = await GetLearnerNotificationModeUseCase(uow).execute(10)
    updated = await SetLearnerNotificationModeUseCase(uow).execute(
        learner_id=10,
        draft=LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )

    assert listed == (mode,)
    assert fetched == mode
    assert updated is not None
    assert updated.effective_mode == NotificationSystemMode.NEW
    assert repository.updated_learner_mode == (
        10,
        LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )
    assert uow.committed is True


@pytest.mark.asyncio
async def test_setting_learner_mode_to_new_rebuilds_scoped_queue():
    future_start = datetime.now(timezone.utc) + timedelta(days=7)
    rule = NotificationRuleDraft(
        rule_id=7,
        name="lesson_confirmation",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation",
        assignments=(AudienceSelector(scope_type="all_learners"),),
    )
    instances = FakeInstanceRepository()
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
    )
    uow = FakeUnitOfWork(
        settings=repository,
        rules=FakeRuleRepository(rules=(rule,)),
        instances=instances,
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
                    has_homework=False,
                ),
                PreviewEvent(
                    event_type=EventType.LESSON,
                    event_id=618,
                    learner_id=11,
                    starts_at=future_start + timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=False,
                ),
            )
        ),
    )

    updated = await SetLearnerNotificationModeUseCase(uow).execute(
        learner_id=10,
        draft=LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )

    assert updated is not None
    assert instances.cancel_scoped_calls == [
        {
            "rule_ids": (7,),
            "learner_ids": (10,),
            "reason": "learner_notification_mode_changed",
            "statuses": None,
        }
    ]
    assert len(instances.upserted) == 1
    assert instances.upserted[0].learner_id == 10
    assert instances.upserted[0].delivery_enabled is True
    assert uow.committed is True


@pytest.mark.asyncio
async def test_rebuild_learner_notification_queue_uses_existing_effective_mode():
    future_start = datetime.now(timezone.utc) + timedelta(days=7)
    rule = NotificationRuleDraft(
        rule_id=7,
        name="lesson_confirmation",
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Привет, {student_name}!",
        template_key="lesson_confirmation",
        assignments=(AudienceSelector(scope_type="all_learners"),),
    )
    instances = FakeInstanceRepository()
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
        learner_modes=(
            LearnerNotificationModeRecord(
                learner_id=10,
                display_name="Вика",
                mode_override=NotificationSystemMode.INHERIT,
                effective_mode=NotificationSystemMode.NEW,
            ),
        ),
    )
    uow = FakeUnitOfWork(
        settings=repository,
        rules=FakeRuleRepository(rules=(rule,)),
        instances=instances,
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
                    has_homework=False,
                ),
            )
        ),
    )

    rebuilt = await RebuildLearnerNotificationQueueUseCase(uow).execute(
        learner_id=10,
        reason="learner_notifications_changed",
        commit=False,
    )

    assert rebuilt is not None
    assert instances.cancel_scoped_calls == [
        {
            "rule_ids": (7,),
            "learner_ids": (10,),
            "reason": "learner_notifications_changed",
            "statuses": None,
        }
    ]
    assert len(instances.upserted) == 1
    assert instances.upserted[0].learner_id == 10
    assert instances.upserted[0].delivery_enabled is True
    assert uow.committed is False


@pytest.mark.asyncio
async def test_setting_learner_mode_to_new_skips_past_due_package_renewal_instances():
    rule = NotificationRuleDraft(
        rule_id=8,
        name="package_renewal",
        category=CategoryKey.PACKAGE_RENEWAL,
        event_type=EventType.PACKAGE,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": 0, "local_time": "10:00"},
        priority=Priority.NORMAL,
        template_body="Продлим пакет?",
        template_key="package_renewal",
        assignments=(AudienceSelector(scope_type="all_learners"),),
    )
    instances = FakeInstanceRepository()
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY),
    )
    uow = FakeUnitOfWork(
        settings=repository,
        rules=FakeRuleRepository(rules=(rule,)),
        instances=instances,
        audience_resolver=FakeAudienceResolver(
            recipients=(PreviewRecipient(learner_id=10, display_name="Вика"),)
        ),
        events=FakeEventRepository(
            events=(
                PreviewEvent(
                    event_type=EventType.PACKAGE,
                    event_id=85,
                    learner_id=10,
                    starts_at=datetime.now(timezone.utc) - timedelta(days=1),
                    timezone="UTC",
                    package_status="active",
                ),
            )
        ),
    )

    updated = await SetLearnerNotificationModeUseCase(uow).execute(
        learner_id=10,
        draft=LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )

    assert updated is not None
    assert instances.cancel_scoped_calls == [
        {
            "rule_ids": (8,),
            "learner_ids": (10,),
            "reason": "learner_notification_mode_changed",
            "statuses": None,
        }
    ]
    assert instances.upserted == ()
    assert uow.committed is True
