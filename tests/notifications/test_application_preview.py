from dataclasses import dataclass, replace
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from notifications.application.dto import (
    AudienceSelector,
    NotificationRuleDraft,
    PreviewEvent,
    PreviewRecipient,
)
from notifications.application.preview import PreviewRulesUseCase, PreviewRuleUseCase
from notifications.application.dto import CombinedPreviewInstance
from notifications.domain.entities import NotificationPreference, QuietHours
from notifications.domain.enums import CategoryKey, EventType, PreferenceScope, TriggerType

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _event_package_id(event: PreviewEvent):
    return event.event_id if event.event_type == EventType.PACKAGE else event.metadata.get("package_id")


@dataclass
class FakeAudienceResolver:
    recipients: tuple[PreviewRecipient, ...]

    async def resolve_recipients(self, assignments):
        return self.recipients


@dataclass
class FakeEventRepository:
    events: tuple[PreviewEvent, ...]

    async def list_events_for_recipients(
        self, *, event_type, learner_ids, included_package_ids=None,
        excluded_package_ids=(), horizon_days, limit, offset=0
    ):
        events = tuple(
            event
            for event in self.events
            if event.event_type == event_type and event.learner_id in learner_ids
            and _event_package_id(event) not in excluded_package_ids
            and (included_package_ids is None or _event_package_id(event) in included_package_ids)
        )
        return events[offset:offset + limit]


@dataclass
class FakePreferenceRepository:
    global_preference: NotificationPreference | None = None
    learner_preferences: dict[int, NotificationPreference | None] | None = None
    group_preferences: dict[int, tuple[NotificationPreference, ...]] | None = None
    learner_calls: int = 0
    group_calls: int = 0

    async def get_global_preference(self):
        return self.global_preference

    async def get_group_preferences_for_learner(self, learner_id):
        self.group_calls += 1
        return (self.group_preferences or {}).get(learner_id, ())

    async def get_learner_preference(self, learner_id):
        self.learner_calls += 1
        return (self.learner_preferences or {}).get(learner_id)


@dataclass
class FakePreviewUnitOfWork:
    audience_resolver: FakeAudienceResolver
    events: FakeEventRepository
    preferences: FakePreferenceRepository


def _draft(category: CategoryKey = CategoryKey.LESSON_CONFIRMATION) -> NotificationRuleDraft:
    return NotificationRuleDraft(
        rule_id=1,
        name="Подтверждение урока",
        category=category,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Привет, {student_name}! Урок в {lesson_time}.",
        template_key=category.value,
        assignments=(AudienceSelector(scope_type="learner", scope_id=10),),
    )


def _uow(
    *,
    recipient: PreviewRecipient | None = None,
    event: PreviewEvent | None = None,
    preference: NotificationPreference | None = None,
) -> FakePreviewUnitOfWork:
    return FakePreviewUnitOfWork(
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
                    starts_at=datetime(2026, 4, 8, 20, 0, tzinfo=MOSCOW_TZ),
                    timezone="Europe/Moscow",
                    package_status="active",
                    lesson_status="scheduled",
                    has_homework=True,
                ),
            )
        ),
        preferences=FakePreferenceRepository(global_preference=preference),
    )


@pytest.mark.asyncio
async def test_preview_rule_schedules_lesson_notification():
    result = await PreviewRuleUseCase(_uow()).execute(_draft())

    assert result.warnings == ()
    assert len(result.instances) == 1
    instance = result.instances[0]
    assert instance.status == "scheduled"
    assert instance.scheduled_for == datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    assert instance.effective_scheduled_for == datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc)
    assert instance.explanation["learner_name"] == "Вика"
    assert instance.explanation["event_starts_at"] == "2026-04-08T20:00:00+03:00"
    assert instance.explanation["event_timezone"] == "Europe/Moscow"


@pytest.mark.asyncio
async def test_preview_rule_package_assignment_does_not_include_other_packages():
    starts_at = datetime(2026, 4, 8, 20, 0, tzinfo=MOSCOW_TZ)
    uow = _uow(
        event=PreviewEvent(
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            starts_at=starts_at,
            package_status="active",
            lesson_status="scheduled",
            metadata={"package_id": 101},
        )
    )
    uow.events.events += (
        PreviewEvent(
            event_type=EventType.LESSON,
            event_id=618,
            learner_id=10,
            starts_at=starts_at,
            package_status="active",
            lesson_status="scheduled",
            metadata={"package_id": 102},
        ),
    )
    draft = replace(
        _draft(),
        assignments=(AudienceSelector(scope_type="package", scope_id=101),),
    )

    result = await PreviewRuleUseCase(uow).execute(draft)

    assert [instance.event_id for instance in result.instances] == [617]


@pytest.mark.asyncio
async def test_preview_rule_package_exclusion_only_excludes_that_package():
    starts_at = datetime(2026, 4, 8, 20, 0, tzinfo=MOSCOW_TZ)
    uow = _uow(
        event=PreviewEvent(
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            starts_at=starts_at,
            package_status="active",
            lesson_status="scheduled",
            metadata={"package_id": 101},
        )
    )
    uow.events.events += (
        PreviewEvent(
            event_type=EventType.LESSON,
            event_id=618,
            learner_id=10,
            starts_at=starts_at,
            package_status="active",
            lesson_status="scheduled",
            metadata={"package_id": 102},
        ),
    )
    draft = replace(
        _draft(),
        assignments=(
            AudienceSelector(scope_type="learner", scope_id=10),
            AudienceSelector(scope_type="package", scope_id=101, is_exclusion=True),
        ),
    )

    result = await PreviewRuleUseCase(uow).execute(draft)

    assert [instance.event_id for instance in result.instances] == [618]


@pytest.mark.asyncio
async def test_preview_rule_loads_preferences_once_per_learner():
    uow = _uow()
    first = uow.events.events[0]
    uow.events.events += (replace(first, event_id=618),)

    result = await PreviewRuleUseCase(uow).execute(_draft())

    assert len(result.instances) == 2
    assert uow.preferences.learner_calls == 1
    assert uow.preferences.group_calls == 1


@pytest.mark.asyncio
async def test_preview_rule_shifts_quiet_hours():
    preference = NotificationPreference(
        scope_type=PreferenceScope.GLOBAL,
        quiet_hours=QuietHours(start=time(9, 30), end=time(12, 0)),
    )

    result = await PreviewRuleUseCase(_uow(preference=preference)).execute(_draft())

    instance = result.instances[0]
    assert instance.effective_scheduled_for == datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)
    assert instance.warnings == ("quiet_hours_shifted",)


@pytest.mark.asyncio
async def test_preview_rule_returns_skipped_instance_when_recipient_has_no_contact():
    recipient = PreviewRecipient(learner_id=10, display_name="Вика", has_contact=False)

    result = await PreviewRuleUseCase(_uow(recipient=recipient)).execute(_draft())

    instance = result.instances[0]
    assert instance.status == "skipped"
    assert instance.reason == "missing_contact"


@pytest.mark.asyncio
async def test_preview_rule_warns_for_active_lesson_slot_conflict():
    event = PreviewEvent(
        event_type=EventType.LESSON,
        event_id=617,
        learner_id=10,
        starts_at=datetime(2026, 4, 8, 20, 0, tzinfo=MOSCOW_TZ),
        timezone="Europe/Moscow",
        package_status="active",
        lesson_status="scheduled",
        has_homework=True,
        metadata={
            "calendar_conflict_count": 2,
            "calendar_conflict_lesson_ids": (581, 617),
            "calendar_conflict_package_ids": (64, 74),
        },
    )

    result = await PreviewRuleUseCase(_uow(event=event)).execute(_draft())

    instance = result.instances[0]
    assert instance.warnings == ("calendar_conflict:active_lessons_same_slot",)
    assert instance.explanation["calendar_conflict"] == {
        "type": "active_lessons_same_slot",
        "count": 2,
        "lesson_ids": [581, 617],
        "package_ids": [64, 74],
    }


@pytest.mark.asyncio
async def test_preview_rule_warns_for_unknown_template_variables():
    draft = NotificationRuleDraft(
        rule_id=1,
        name="Broken",
        category=CategoryKey.CUSTOM,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Привет, {nickname}.",
        assignments=(AudienceSelector(scope_type="learner", scope_id=10),),
    )

    result = await PreviewRuleUseCase(_uow()).execute(draft)

    assert result.warnings == ("unknown_template_variables:nickname",)


@pytest.mark.asyncio
async def test_preview_rules_combines_confirmation_and_homework():
    confirmation = _draft(CategoryKey.LESSON_CONFIRMATION)
    homework = NotificationRuleDraft(
        rule_id=2,
        name="Домашка",
        category=CategoryKey.HOMEWORK,
        event_type=EventType.LESSON,
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        trigger_config={"days": -1, "local_time": "10:00"},
        template_body="Не забудь домашку, {student_name}.",
        template_key="homework",
        assignments=(AudienceSelector(scope_type="learner", scope_id=10),),
    )

    result = await PreviewRulesUseCase(_uow()).execute((confirmation, homework))

    assert len(result.instances) == 1
    combined = result.instances[0]
    assert isinstance(combined, CombinedPreviewInstance)
    assert combined.warnings == ("combined",)
    assert [component.category for component in combined.components] == [
        CategoryKey.LESSON_CONFIRMATION,
        CategoryKey.HOMEWORK,
    ]
