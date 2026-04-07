from datetime import datetime, time, timezone
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    NotificationSystemMode,
    PreferenceScope,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
)
from notifications.infrastructure.models import (
    NotificationAssignment,
    NotificationCategory,
    NotificationPreference,
    NotificationRule,
    NotificationSystemSetting,
    NotificationTemplate,
)
from notifications.infrastructure.repositories import (
    _learner_mode_record,
    _active_rules_for_group_stmt,
    _active_rules_stmt,
    _group_member_record_from_row,
    _group_members_stmt,
    _group_record_from_count_row,
    _lesson_event_from_row,
    _lesson_events_stmt,
    _learner_groups_with_counts_stmt,
    _notification_templates_stmt,
    _notification_rules_stmt,
    _package_event_from_row,
    _preference_from_model,
    _settings_record_from_models,
    map_notification_rule_to_record,
    _template_record_from_model,
    _recipient_from_row,
    map_notification_rule_to_draft,
)


def test_map_notification_rule_to_draft_uses_template_and_assignments():
    category = NotificationCategory(key="homework", display_name="Домашка")
    template = NotificationTemplate(key="homework_default", name="Домашка", body="Привет")
    rule = NotificationRule(
        id=42,
        name="Домашка за день",
        category=category,
        template=template,
        event_type="lesson",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -1, "local_time": "10:00"},
        priority="normal",
        combine_policy_key="lesson_confirmation_homework",
        assignments=[
            NotificationAssignment(scope_type="group", scope_id=7, is_exclusion=False),
            NotificationAssignment(scope_type="learner", scope_id=10, is_exclusion=True),
        ],
    )

    draft = map_notification_rule_to_draft(rule)

    assert draft.rule_id == 42
    assert draft.category == CategoryKey.HOMEWORK
    assert draft.event_type == EventType.LESSON
    assert draft.trigger_type == TriggerType.DAY_OFFSET_AT_TIME
    assert draft.priority == Priority.NORMAL
    assert draft.template_body == "Привет"
    assert draft.template_key == "homework_default"
    assert draft.combine_policy_key == "lesson_confirmation_homework"
    assignment_summary = [
        (assignment.scope_type, assignment.scope_id, assignment.is_exclusion)
        for assignment in draft.assignments
    ]
    assert assignment_summary == [
        ("group", 7, False),
        ("learner", 10, True),
    ]


def test_map_notification_rule_to_record_preserves_management_fields():
    category = NotificationCategory(key="homework", display_name="Домашка")
    template = NotificationTemplate(id=3, key="homework_default", name="Домашка", body="Привет")
    rule = NotificationRule(
        id=42,
        tenant_id=1,
        name="Домашка за день",
        category=category,
        template_id=3,
        template=template,
        inline_template_format="plain_text",
        description="Перед уроком",
        event_type="lesson",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -1, "local_time": "10:00"},
        priority="normal",
        status="active",
        combine_policy_key="lesson_confirmation_homework",
        delivery_channel="telegram",
        cap_mode="warn_only",
        quiet_hours_mode="shift",
        bypass_quiet_hours=False,
        assignments=[
            NotificationAssignment(scope_type="group", scope_id=7, is_exclusion=False),
        ],
    )

    record = map_notification_rule_to_record(rule)

    assert record.rule_id == 42
    assert record.tenant_id == 1
    assert record.category == CategoryKey.HOMEWORK
    assert record.template_id == 3
    assert record.template_key == "homework_default"
    assert record.status == RuleStatus.ACTIVE
    assert record.cap_mode == CapMode.WARN_ONLY
    assert record.quiet_hours_mode == QuietHoursMode.SHIFT
    assert record.assignments[0].scope_type == "group"


def test_preference_mapper_parses_quiet_hours_and_category_preferences():
    model = NotificationPreference(
        scope_type="learner",
        scope_id=10,
        notifications_enabled=True,
        quiet_hours_start="21:00",
        quiet_hours_end="09:00",
        timezone="Europe/Moscow",
        daily_cap=5,
        cap_mode="warn_only",
        category_preferences={"homework": False},
    )

    preference = _preference_from_model(model)

    assert preference is not None
    assert preference.scope_type == PreferenceScope.LEARNER
    assert preference.scope_id == 10
    assert preference.quiet_hours is not None
    assert preference.quiet_hours.start == time(21, 0)
    assert preference.quiet_hours.end == time(9, 0)
    assert preference.category_enabled == {CategoryKey.HOMEWORK: False}


def test_settings_mappers_apply_defaults_and_effective_learner_mode():
    settings = _settings_record_from_models(
        tenant_id=1,
        system_setting=NotificationSystemSetting(mode="shadow"),
        global_preference=NotificationPreference(
            notifications_enabled=True,
            quiet_hours_start="21:00",
            quiet_hours_end="09:00",
            timezone="Europe/Moscow",
            daily_cap=3,
            cap_mode="warn_only",
            category_preferences={"homework": False},
        ),
    )
    inherited = _learner_mode_record(
        learner_id=10,
        display_name="Вика",
        mode_override=NotificationSystemMode.INHERIT,
        tenant_mode=NotificationSystemMode.SHADOW,
        updated_at=None,
    )

    assert settings.mode == NotificationSystemMode.SHADOW
    assert settings.daily_cap == 3
    assert settings.category_preferences == {"homework": False}
    assert inherited.mode_override == NotificationSystemMode.INHERIT
    assert inherited.effective_mode == NotificationSystemMode.SHADOW


def test_lesson_events_statement_filters_by_horizon_and_tenant():
    starts_at = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
    ends_at = datetime(2026, 5, 7, 0, 0, tzinfo=timezone.utc)

    stmt = _lesson_events_stmt(
        tenant_id=1,
        learner_ids=(10, 11),
        starts_at=starts_at,
        ends_at=ends_at,
        limit=20,
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "JOIN lesson_packages" in compiled
    assert "lessons.tenant_id =" in compiled
    assert "lesson_packages.learner_id IN" in compiled
    assert "lessons.scheduled_at >= %(scheduled_at_1)s" in compiled
    assert "lessons.scheduled_at < %(scheduled_at_2)s" in compiled
    assert "calendar_conflict_count" in compiled
    assert "array_agg" in compiled


def test_active_rules_statement_filters_active_non_archived_rules():
    stmt = _active_rules_stmt(tenant_id=1)

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "notification_rules_v2.tenant_id =" in compiled
    assert "notification_rules_v2.status =" in compiled
    assert "notification_rules_v2.archived_at IS NULL" in compiled


def test_active_rules_for_group_statement_filters_group_assignment():
    stmt = _active_rules_for_group_stmt(tenant_id=1, group_id=7)

    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "JOIN notification_assignments" in compiled
    assert "notification_rules_v2.tenant_id =" in compiled
    assert "notification_rules_v2.status =" in compiled
    assert "notification_assignments.scope_type =" in compiled
    assert "notification_assignments.scope_id =" in compiled
    assert "notification_assignments.is_exclusion IS false" in compiled


def test_notification_rules_statement_filters_archived_by_default():
    stmt = _notification_rules_stmt(tenant_id=1, include_archived=False)

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_rules_v2.tenant_id =" in compiled
    assert "notification_rules_v2.status !=" in compiled
    assert "notification_rules_v2.archived_at IS NULL" in compiled


def test_group_statements_filter_by_tenant_and_group():
    groups_stmt = _learner_groups_with_counts_stmt(tenant_id=1)
    members_stmt = _group_members_stmt(tenant_id=1, group_id=7)

    compiled_groups = str(groups_stmt.compile(dialect=postgresql.dialect()))
    compiled_members = str(members_stmt.compile(dialect=postgresql.dialect()))

    assert "learner_groups.tenant_id =" in compiled_groups
    assert "count(group_members.id) FILTER (WHERE group_members.status =" in compiled_groups
    assert "group_members.group_id =" in compiled_members
    assert "JOIN learners" in compiled_members


def test_template_statement_includes_system_and_tenant_templates():
    stmt = _notification_templates_stmt(tenant_id=1, include_archived=False)

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_templates.tenant_id =" in compiled
    assert "notification_templates.tenant_id IS NULL" in compiled
    assert "notification_templates.archived_at IS NULL" in compiled


def test_preview_row_mappers_preserve_recipient_and_event_context():
    recipient = _recipient_from_row(
        SimpleNamespace(
            learner_id=10,
            display_name="Вика",
            notifications_enabled=False,
            chat_id=None,
        )
    )

    assert recipient.learner_id == 10
    assert recipient.notifications_enabled is False
    assert recipient.has_contact is False

    starts_at = datetime(2026, 4, 8, 17, 0, tzinfo=timezone.utc)
    lesson_event = _lesson_event_from_row(
        SimpleNamespace(
            event_id=617,
            learner_id=10,
            starts_at=starts_at,
            duration_minutes=60,
            timezone="Europe/Moscow",
            package_status="active",
            lesson_status="scheduled",
            has_homework=True,
            homework_due_at=None,
            sequence_index=5,
            package_id=64,
            package_title="Вика март",
            calendar_conflict_count=2,
            calendar_conflict_lesson_ids=[581, 617],
            calendar_conflict_package_ids=[64, 74],
        )
    )
    assert lesson_event.event_type == EventType.LESSON
    assert lesson_event.ends_at == datetime(2026, 4, 8, 18, 0, tzinfo=timezone.utc)
    assert lesson_event.metadata["package_title"] == "Вика март"
    assert lesson_event.metadata["calendar_conflict_count"] == 2
    assert lesson_event.metadata["calendar_conflict_lesson_ids"] == (581, 617)
    assert lesson_event.metadata["calendar_conflict_package_ids"] == (64, 74)

    package_event = _package_event_from_row(
        SimpleNamespace(
            event_id=64,
            learner_id=10,
            starts_at=starts_at,
            timezone="Europe/Moscow",
            package_status="active",
            package_title="Вика март",
        )
    )
    assert package_event.event_type == EventType.PACKAGE
    assert package_event.metadata["package_title"] == "Вика март"


def test_group_row_mappers_preserve_member_counts_and_member_context():
    group = _group_record_from_count_row(
        SimpleNamespace(
            id=7,
            name="TOPIK",
            description="Speaking",
            color="#3366ff",
            status="active",
            member_count=2,
            created_at=None,
            updated_at=None,
        )
    )
    member = _group_member_record_from_row(
        SimpleNamespace(
            learner_id=10,
            display_name="Вика",
            status="active",
            joined_at=None,
            left_at=None,
        )
    )

    assert group.group_id == 7
    assert group.member_count == 2
    assert member.learner_id == 10
    assert member.display_name == "Вика"


def test_template_mapper_preserves_versioning_fields():
    category = NotificationCategory(key="homework", display_name="Домашка")
    template = NotificationTemplate(
        id=3,
        tenant_id=1,
        category=category,
        key="homework",
        name="Домашка",
        body="Привет",
        description=None,
        locale="ru",
        template_format="plain_text",
        version=2,
        system=False,
        based_on_template_id=1,
    )

    record = _template_record_from_model(template)

    assert record.template_id == 3
    assert record.category == CategoryKey.HOMEWORK
    assert record.version == 2
    assert record.based_on_template_id == 1
