from database.models import Base, Lesson
from notifications.infrastructure.models import (
    GroupMember,
    LessonParticipantState,
    NotificationDeliveryAttempt,
    NotificationInstance,
    NotificationAssignment,
    NotificationRule,
    NotificationTemplate,
    NotificationResponse,
)


def test_notification_tables_are_registered_in_shared_metadata():
    expected_tables = {
        "notification_categories",
        "notification_templates",
        "notification_rules_v2",
        "notification_assignments",
        "notification_preferences",
        "notification_instances",
        "notification_instance_components",
        "notification_delivery_attempts",
        "notification_responses",
        "lesson_participant_states",
        "notification_audit_log",
        "notification_jobs",
        "notification_system_settings",
        "learner_notification_modes",
        "learner_groups",
        "group_members",
    }

    assert expected_tables.issubset(Base.metadata.tables)


def test_lesson_homework_fields_are_available_for_notification_eligibility():
    assert hasattr(Lesson, "has_homework")
    assert hasattr(Lesson, "homework_text")


def test_notification_response_is_unique_per_instance():
    constraints = {constraint.name for constraint in NotificationResponse.__table__.constraints}

    assert "uq_notification_response_instance" in constraints


def test_notification_instance_has_semantic_dedupe_index():
    indexes = {index.name for index in NotificationInstance.__table__.indexes}

    assert "uq_notification_instances_dedupe" in indexes
    dedupe_index = next(
        index
        for index in NotificationInstance.__table__.indexes
        if index.name == "uq_notification_instances_dedupe"
    )
    assert "event_key" in {column.name for column in dedupe_index.columns}
    assert "event_id" not in {column.name for column in dedupe_index.columns}


def test_notification_template_uniqueness_handles_system_and_tenant_rows():
    indexes = {index.name: index for index in NotificationTemplate.__table__.indexes}

    assert "uq_notification_templates_system_key_locale_version" in indexes
    assert "uq_notification_templates_tenant_key_locale_version" in indexes

    system_index = indexes["uq_notification_templates_system_key_locale_version"]
    tenant_index = indexes["uq_notification_templates_tenant_key_locale_version"]

    assert {column.name for column in system_index.columns} == {"key", "locale", "version"}
    assert {column.name for column in tenant_index.columns} == {
        "tenant_id",
        "key",
        "locale",
        "version",
    }
    assert str(system_index.dialect_options["postgresql"]["where"]).endswith("tenant_id IS NULL")
    assert str(tenant_index.dialect_options["postgresql"]["where"]).endswith("tenant_id IS NOT NULL")


def test_notification_rule_presets_are_unique_per_tenant_when_present():
    indexes = {index.name: index for index in NotificationRule.__table__.indexes}

    assert "uq_notification_rules_tenant_preset_key" in indexes
    preset_index = indexes["uq_notification_rules_tenant_preset_key"]
    assert {column.name for column in preset_index.columns} == {"tenant_id", "preset_key"}
    assert str(preset_index.dialect_options["postgresql"]["where"]).endswith(
        "preset_key IS NOT NULL"
    )


def test_notification_assignment_uniqueness_handles_nullable_scope_id():
    indexes = {index.name: index for index in NotificationAssignment.__table__.indexes}

    assert "uq_notification_assignments_rule_scope_with_id" in indexes
    assert "uq_notification_assignments_rule_scope_without_id" in indexes

    with_id = indexes["uq_notification_assignments_rule_scope_with_id"]
    without_id = indexes["uq_notification_assignments_rule_scope_without_id"]

    assert {column.name for column in with_id.columns} == {
        "rule_id",
        "scope_type",
        "scope_id",
        "is_exclusion",
    }
    assert {column.name for column in without_id.columns} == {
        "rule_id",
        "scope_type",
        "is_exclusion",
    }
    assert str(with_id.dialect_options["postgresql"]["where"]).endswith("scope_id IS NOT NULL")
    assert str(without_id.dialect_options["postgresql"]["where"]).endswith("scope_id IS NULL")


def test_delivery_attempts_are_unique_per_instance_attempt_number():
    constraints = {constraint.name for constraint in NotificationDeliveryAttempt.__table__.constraints}

    assert "uq_notification_attempt_instance_no" in constraints


def test_lesson_participant_state_is_unique_per_lesson_and_learner():
    constraints = {constraint.name for constraint in LessonParticipantState.__table__.constraints}

    assert "uq_lesson_participant_state_lesson_learner" in constraints


def test_group_membership_has_active_unique_index():
    indexes = {index.name for index in GroupMember.__table__.indexes}

    assert "uq_group_members_active_membership" in indexes
