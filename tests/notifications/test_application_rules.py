from dataclasses import dataclass, field

import pytest

from notifications.application.dto import (
    AudienceSelector,
    NotificationAuditLogDraft,
    NotificationJobDraft,
    NotificationRuleCreateDraft,
    NotificationRuleRecord,
    NotificationRuleUpdateDraft,
    NotificationSettingsRecord,
)
from notifications.application.rules import (
    ActivateNotificationRuleUseCase,
    ArchiveNotificationRuleUseCase,
    CreateNotificationRuleUseCase,
    GetNotificationRuleUseCase,
    ListNotificationRulesUseCase,
    PauseNotificationRuleUseCase,
    UpdateNotificationRuleUseCase,
)
from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    NotificationSystemMode,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
)


def _record(*, rule_id: int = 1, status: RuleStatus = RuleStatus.DRAFT) -> NotificationRuleRecord:
    return NotificationRuleRecord(
        rule_id=rule_id,
        tenant_id=1,
        preset_key=None,
        category=CategoryKey.HOMEWORK,
        template_id=3,
        template_key="homework",
        inline_template_body=None,
        inline_template_format="plain_text",
        name="Домашка",
        description=None,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        priority=Priority.NORMAL,
        status=status,
        combine_policy_key="lesson_confirmation_homework",
        delivery_channel="telegram",
        cap_mode=CapMode.WARN_ONLY,
        quiet_hours_mode=QuietHoursMode.SHIFT,
        bypass_quiet_hours=False,
        assignments=(AudienceSelector(scope_type="group", scope_id=7),),
    )


@dataclass
class FakeRuleRepository:
    rules: tuple[NotificationRuleRecord, ...] = field(default_factory=tuple)
    created: list[NotificationRuleCreateDraft] = field(default_factory=list)
    updated: list[tuple[int, NotificationRuleUpdateDraft]] = field(default_factory=list)
    statuses: list[tuple[int, str]] = field(default_factory=list)

    async def list_rules(self, *, include_archived=False):
        return self.rules

    async def get_rule(self, rule_id):
        return next((rule for rule in self.rules if rule.rule_id == rule_id), None)

    async def create_rule(self, draft):
        self.created.append(draft)
        return _record(rule_id=1, status=draft.status)

    async def update_rule(self, rule_id, draft):
        self.updated.append((rule_id, draft))
        existing = await self.get_rule(rule_id)
        return _record(
            rule_id=rule_id,
            status=draft.status or (existing.status if existing else RuleStatus.DRAFT),
        )

    async def set_rule_status(self, rule_id, status):
        self.statuses.append((rule_id, status))
        return _record(rule_id=rule_id, status=RuleStatus(status))


@dataclass
class FakeAuditLogRepository:
    records: list[NotificationAuditLogDraft] = field(default_factory=list)

    async def record_audit(self, draft):
        self.records.append(draft)
        return None


@dataclass
class FakeInstanceRepository:
    cancel_rule_calls: list[dict] = field(default_factory=list)

    async def cancel_future_instances_for_rules(self, *, rule_ids, reason: str):
        self.cancel_rule_calls.append({"rule_ids": rule_ids, "reason": reason})
        return 0


@dataclass
class FakeJobRepository:
    created: list[NotificationJobDraft] = field(default_factory=list)

    async def create_job(self, draft):
        self.created.append(draft)
        return None


@dataclass
class FakeSettingsRepository:
    mode: NotificationSystemMode = NotificationSystemMode.NEW

    async def get_settings(self):
        return NotificationSettingsRecord(tenant_id=1, mode=self.mode)


@dataclass
class FakeUnitOfWork:
    rules: FakeRuleRepository
    instances: FakeInstanceRepository = field(default_factory=FakeInstanceRepository)
    audit_log: FakeAuditLogRepository = field(default_factory=FakeAuditLogRepository)
    jobs: FakeJobRepository = field(default_factory=FakeJobRepository)
    settings: FakeSettingsRepository = field(default_factory=FakeSettingsRepository)
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_list_and_get_rules_do_not_commit():
    rule = _record(rule_id=1)
    uow = FakeUnitOfWork(rules=FakeRuleRepository(rules=(rule,)))

    listed = await ListNotificationRulesUseCase(uow).execute()
    fetched = await GetNotificationRuleUseCase(uow).execute(1)

    assert listed == (rule,)
    assert fetched == rule
    assert uow.committed is False


@pytest.mark.asyncio
async def test_create_and_update_rules_commit_changes():
    repository = FakeRuleRepository()
    uow = FakeUnitOfWork(rules=repository)
    create_draft = NotificationRuleCreateDraft(
        category=CategoryKey.HOMEWORK,
        name="Домашка",
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_id=3,
        assignments=(AudienceSelector(scope_type="group", scope_id=7),),
    )
    update_draft = NotificationRuleUpdateDraft(name="Домашка 2")

    created = await CreateNotificationRuleUseCase(uow).execute(create_draft)
    updated = await UpdateNotificationRuleUseCase(uow).execute(rule_id=created.rule_id, draft=update_draft)

    assert repository.created == [create_draft]
    assert repository.updated == [(1, update_draft)]
    assert [record.action for record in uow.audit_log.records] == ["created", "updated"]
    assert [record.entity_type for record in uow.audit_log.records] == [
        "notification_rule",
        "notification_rule",
    ]
    assert updated is not None
    assert updated.name == "Домашка"
    assert uow.committed


@pytest.mark.asyncio
async def test_status_use_cases_commit_status_transition():
    repository = FakeRuleRepository()
    uow = FakeUnitOfWork(rules=repository)

    activated = await ActivateNotificationRuleUseCase(uow).execute(1)
    paused = await PauseNotificationRuleUseCase(uow).execute(1)
    archived = await ArchiveNotificationRuleUseCase(uow).execute(1)

    assert repository.statuses == [
        (1, "active"),
        (1, "paused"),
        (1, "archived"),
    ]
    assert [draft.scope["reason"] for draft in uow.jobs.created] == ["rule_activated"]
    assert uow.jobs.created[0].scope["delivery_enabled"] is True
    assert uow.jobs.created[0].scope["shadow"] is False
    assert uow.instances.cancel_rule_calls == [
        {"rule_ids": (1,), "reason": "rule_not_active"},
        {"rule_ids": (1,), "reason": "rule_not_active"},
    ]
    assert [record.action for record in uow.audit_log.records] == ["activated", "paused", "archived"]
    assert activated is not None and activated.status == RuleStatus.ACTIVE
    assert paused is not None and paused.status == RuleStatus.PAUSED
    assert archived is not None and archived.status == RuleStatus.ARCHIVED
    assert uow.committed


@pytest.mark.asyncio
async def test_update_rule_cancels_future_instances_when_status_becomes_inactive():
    repository = FakeRuleRepository(rules=(_record(rule_id=1, status=RuleStatus.ACTIVE),))
    uow = FakeUnitOfWork(rules=repository)

    updated = await UpdateNotificationRuleUseCase(uow).execute(
        rule_id=1,
        draft=NotificationRuleUpdateDraft(status=RuleStatus.PAUSED),
    )

    assert updated is not None
    assert uow.instances.cancel_rule_calls == [
        {"rule_ids": (1,), "reason": "rule_not_active"}
    ]


@pytest.mark.asyncio
async def test_update_active_rule_cancels_old_schedule_and_queues_rebuild():
    repository = FakeRuleRepository(rules=(_record(rule_id=1, status=RuleStatus.ACTIVE),))
    uow = FakeUnitOfWork(rules=repository)

    updated = await UpdateNotificationRuleUseCase(uow).execute(
        rule_id=1,
        draft=NotificationRuleUpdateDraft(trigger_config={"days": -2, "local_time": "10:00"}),
    )

    assert updated is not None and updated.status == RuleStatus.ACTIVE
    assert uow.instances.cancel_rule_calls == [
        {"rule_ids": (1,), "reason": "rule_updated"}
    ]
    assert [draft.scope["reason"] for draft in uow.jobs.created] == ["rule_updated"]
