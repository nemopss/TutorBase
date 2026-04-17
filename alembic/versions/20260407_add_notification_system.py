"""Add notification system bounded context.

Revision ID: 20260407_notifications
Revises: 20251217_learner_schedule
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import json


revision = "20260407_notifications"
down_revision = "20251217_learner_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("has_homework", sa.Boolean(), nullable=True))
    op.add_column("lessons", sa.Column("homework_text", sa.Text(), nullable=True))

    op.create_table(
        "notification_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system", sa.Boolean(), nullable=False),
        sa.Column("default_priority", sa.String(length=16), nullable=False),
        sa.Column("default_counts_towards_daily_cap", sa.Boolean(), nullable=False),
        sa.Column("default_can_bypass_quiet_hours", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    categories = sa.table(
        "notification_categories",
        sa.column("key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("system", sa.Boolean),
        sa.column("default_priority", sa.String),
        sa.column("default_counts_towards_daily_cap", sa.Boolean),
        sa.column("default_can_bypass_quiet_hours", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        categories,
        [
            _category("lesson_confirmation", "Подтверждение урока"),
            _category("lesson_reminder", "Напоминание об уроке"),
            _category("homework", "Домашнее задание"),
            _category("package_renewal", "Продление пакета"),
            _category("payment", "Оплата"),
            _category("custom", "Произвольное уведомление"),
            _category("teacher_alert", "Уведомление учителю", priority="high", can_bypass_quiet_hours=True),
        ],
    )

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("template_format", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_rich_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("based_on_template_id", sa.Integer(), nullable=True),
        sa.Column("system", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["based_on_template_id"], ["notification_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["notification_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_templates_tenant_id", "notification_templates", ["tenant_id"])
    op.create_index("ix_notification_templates_tenant_category", "notification_templates", ["tenant_id", "category_id"])
    op.create_index(
        "uq_notification_templates_tenant_key_locale_version",
        "notification_templates",
        ["tenant_id", "key", "locale", "version"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_notification_templates_system_key_locale_version",
        "notification_templates",
        ["key", "locale", "version"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    _seed_system_templates()

    op.create_table(
        "notification_rules_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("preset_key", sa.String(length=128), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("inline_template_body", sa.Text(), nullable=True),
        sa.Column("inline_template_format", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("combine_policy_key", sa.String(length=64), nullable=True),
        sa.Column("delivery_channel", sa.String(length=32), nullable=False),
        sa.Column("cap_mode", sa.String(length=32), nullable=False),
        sa.Column("quiet_hours_mode", sa.String(length=32), nullable=False),
        sa.Column("bypass_quiet_hours", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["notification_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_rules_v2_tenant_id", "notification_rules_v2", ["tenant_id"])
    op.create_index("ix_notification_rules_tenant_status", "notification_rules_v2", ["tenant_id", "status"])
    op.create_index("ix_notification_rules_tenant_event", "notification_rules_v2", ["tenant_id", "event_type"])
    op.create_index(
        "uq_notification_rules_tenant_preset_key",
        "notification_rules_v2",
        ["tenant_id", "preset_key"],
        unique=True,
        postgresql_where=sa.text("preset_key IS NOT NULL"),
    )

    op.create_table(
        "notification_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("is_exclusion", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["notification_rules_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_assignments_tenant_id", "notification_assignments", ["tenant_id"])
    op.create_index("ix_notification_assignments_tenant_scope", "notification_assignments", ["tenant_id", "scope_type", "scope_id"])
    op.create_index(
        "uq_notification_assignments_rule_scope_with_id",
        "notification_assignments",
        ["rule_id", "scope_type", "scope_id", "is_exclusion"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NOT NULL"),
    )
    op.create_index(
        "uq_notification_assignments_rule_scope_without_id",
        "notification_assignments",
        ["rule_id", "scope_type", "is_exclusion"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NULL"),
    )
    _seed_recommended_draft_rules()

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=True),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("daily_cap", sa.Integer(), nullable=True),
        sa.Column("cap_mode", sa.String(length=32), nullable=True),
        sa.Column("category_preferences", sa.JSON(), nullable=False),
        sa.Column("set_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_preferences_tenant_id", "notification_preferences", ["tenant_id"])
    op.create_index("ix_notification_preferences_tenant_scope", "notification_preferences", ["tenant_id", "scope_type", "scope_id"])
    op.create_index(
        "uq_notification_preferences_global",
        "notification_preferences",
        ["tenant_id", "scope_type"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NULL"),
    )
    op.create_index(
        "uq_notification_preferences_scoped",
        "notification_preferences",
        ["tenant_id", "scope_type", "scope_id"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NOT NULL"),
    )

    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_jobs_tenant_id", "notification_jobs", ["tenant_id"])
    op.create_index("ix_notification_jobs_tenant_status", "notification_jobs", ["tenant_id", "status"])
    op.create_index("ix_notification_jobs_type_status", "notification_jobs", ["job_type", "status"])

    op.create_table(
        "notification_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("recipient_type", sa.String(length=32), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_reason", sa.String(length=128), nullable=True),
        sa.Column("delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("combination_key", sa.String(length=128), nullable=True),
        sa.Column("manual_overrides", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["notification_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_job_id"], ["notification_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["notification_rules_v2.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_instances_tenant_id", "notification_instances", ["tenant_id"])
    op.create_index("ix_notification_instances_due", "notification_instances", ["status", "delivery_enabled", "effective_scheduled_for"])
    op.create_index("ix_notification_instances_tenant_recipient", "notification_instances", ["tenant_id", "recipient_type", "recipient_id"])
    op.create_index("ix_notification_instances_tenant_event", "notification_instances", ["tenant_id", "event_type", "event_key"])
    op.create_index(
        "uq_notification_instances_dedupe",
        "notification_instances",
        ["tenant_id", "recipient_type", "recipient_id", "event_type", "event_key", "dedupe_key"],
        unique=True,
    )

    op.create_table(
        "notification_instance_components",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("component_key", sa.String(length=128), nullable=False),
        sa.Column("component_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["notification_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["instance_id"], ["notification_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["notification_rules_v2.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_components_instance", "notification_instance_components", ["instance_id"])

    op.create_table(
        "notification_delivery_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("notification_instance_id", sa.Integer(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_chat_id", sa.String(), nullable=True),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("rendered_text", sa.Text(), nullable=True),
        sa.Column("reply_markup_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_instance_id"], ["notification_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_instance_id", "attempt_no", name="uq_notification_attempt_instance_no"),
    )
    op.create_index("ix_notification_delivery_attempts_tenant_id", "notification_delivery_attempts", ["tenant_id"])
    op.create_index("ix_notification_attempts_tenant_status", "notification_delivery_attempts", ["tenant_id", "status"])

    op.create_table(
        "notification_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("notification_instance_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("recipient_type", sa.String(length=32), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=True),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("response_value", sa.String(length=64), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["notification_instance_id"], ["notification_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_responses_tenant_id", "notification_responses", ["tenant_id"])
    op.create_index("ix_notification_responses_tenant_event", "notification_responses", ["tenant_id", "event_type", "event_id"])
    op.create_index("ix_notification_responses_tenant_learner", "notification_responses", ["tenant_id", "learner_id"])

    op.create_table(
        "lesson_participant_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("response_state", sa.String(length=32), nullable=False),
        sa.Column("response_source", sa.String(length=64), nullable=False),
        sa.Column("response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("last_notification_instance_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["last_notification_instance_id"], ["notification_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lesson_id", "learner_id", name="uq_lesson_participant_state_lesson_learner"),
    )
    op.create_index("ix_lesson_participant_states_tenant_id", "lesson_participant_states", ["tenant_id"])
    op.create_index("ix_lesson_participant_states_tenant_lesson", "lesson_participant_states", ["tenant_id", "lesson_id"])
    op.create_index("ix_lesson_participant_states_tenant_learner", "lesson_participant_states", ["tenant_id", "learner_id"])

    op.create_table(
        "notification_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_audit_log_tenant_id", "notification_audit_log", ["tenant_id"])
    op.create_index("ix_notification_audit_tenant_entity", "notification_audit_log", ["tenant_id", "entity_type", "entity_id"])
    op.create_index("ix_notification_audit_tenant_created", "notification_audit_log", ["tenant_id", "created_at"])

    op.create_table(
        "notification_system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_notification_system_settings_tenant_id", "notification_system_settings", ["tenant_id"])

    op.create_table(
        "learner_notification_modes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("mode_override", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id"),
    )
    op.create_index("ix_learner_notification_modes_tenant_id", "learner_notification_modes", ["tenant_id"])
    op.create_index("ix_learner_notification_modes_tenant_learner", "learner_notification_modes", ["tenant_id", "learner_id"])

    op.create_table(
        "learner_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learner_groups_tenant_id", "learner_groups", ["tenant_id"])
    op.create_index("uq_learner_groups_tenant_name", "learner_groups", ["tenant_id", "name"], unique=True)
    op.create_index("ix_learner_groups_tenant_status", "learner_groups", ["tenant_id", "status"])

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["learner_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_members_tenant_id", "group_members", ["tenant_id"])
    op.create_index("ix_group_members_tenant_group", "group_members", ["tenant_id", "group_id"])
    op.create_index("ix_group_members_tenant_learner", "group_members", ["tenant_id", "learner_id"])
    op.create_index(
        "uq_group_members_active_membership",
        "group_members",
        ["group_id", "learner_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_group_members_active_membership", table_name="group_members")
    op.drop_index("ix_group_members_tenant_learner", table_name="group_members")
    op.drop_index("ix_group_members_tenant_group", table_name="group_members")
    op.drop_index("ix_group_members_tenant_id", table_name="group_members")
    op.drop_table("group_members")

    op.drop_index("ix_learner_groups_tenant_status", table_name="learner_groups")
    op.drop_index("uq_learner_groups_tenant_name", table_name="learner_groups")
    op.drop_index("ix_learner_groups_tenant_id", table_name="learner_groups")
    op.drop_table("learner_groups")

    op.drop_index("ix_learner_notification_modes_tenant_learner", table_name="learner_notification_modes")
    op.drop_index("ix_learner_notification_modes_tenant_id", table_name="learner_notification_modes")
    op.drop_table("learner_notification_modes")

    op.drop_index("ix_notification_system_settings_tenant_id", table_name="notification_system_settings")
    op.drop_table("notification_system_settings")

    op.drop_index("ix_notification_audit_tenant_created", table_name="notification_audit_log")
    op.drop_index("ix_notification_audit_tenant_entity", table_name="notification_audit_log")
    op.drop_index("ix_notification_audit_log_tenant_id", table_name="notification_audit_log")
    op.drop_table("notification_audit_log")

    op.drop_index("ix_lesson_participant_states_tenant_learner", table_name="lesson_participant_states")
    op.drop_index("ix_lesson_participant_states_tenant_lesson", table_name="lesson_participant_states")
    op.drop_index("ix_lesson_participant_states_tenant_id", table_name="lesson_participant_states")
    op.drop_table("lesson_participant_states")

    op.drop_index("ix_notification_responses_tenant_learner", table_name="notification_responses")
    op.drop_index("ix_notification_responses_tenant_event", table_name="notification_responses")
    op.drop_index("ix_notification_responses_tenant_id", table_name="notification_responses")
    op.drop_table("notification_responses")

    op.drop_index("ix_notification_attempts_tenant_status", table_name="notification_delivery_attempts")
    op.drop_index("ix_notification_delivery_attempts_tenant_id", table_name="notification_delivery_attempts")
    op.drop_table("notification_delivery_attempts")

    op.drop_index("ix_notification_components_instance", table_name="notification_instance_components")
    op.drop_table("notification_instance_components")

    op.drop_index("uq_notification_instances_dedupe", table_name="notification_instances")
    op.drop_index("ix_notification_instances_tenant_event", table_name="notification_instances")
    op.drop_index("ix_notification_instances_tenant_recipient", table_name="notification_instances")
    op.drop_index("ix_notification_instances_due", table_name="notification_instances")
    op.drop_index("ix_notification_instances_tenant_id", table_name="notification_instances")
    op.drop_table("notification_instances")

    op.drop_index("ix_notification_jobs_type_status", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_tenant_status", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_tenant_id", table_name="notification_jobs")
    op.drop_table("notification_jobs")

    op.drop_index("uq_notification_preferences_scoped", table_name="notification_preferences")
    op.drop_index("uq_notification_preferences_global", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_tenant_scope", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_tenant_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("uq_notification_assignments_rule_scope_without_id", table_name="notification_assignments")
    op.drop_index("uq_notification_assignments_rule_scope_with_id", table_name="notification_assignments")
    op.drop_index("ix_notification_assignments_tenant_scope", table_name="notification_assignments")
    op.drop_index("ix_notification_assignments_tenant_id", table_name="notification_assignments")
    op.drop_table("notification_assignments")

    op.drop_index("ix_notification_rules_tenant_event", table_name="notification_rules_v2")
    op.drop_index("ix_notification_rules_tenant_status", table_name="notification_rules_v2")
    op.drop_index("ix_notification_rules_v2_tenant_id", table_name="notification_rules_v2")
    op.drop_index("uq_notification_rules_tenant_preset_key", table_name="notification_rules_v2")
    op.drop_table("notification_rules_v2")

    op.drop_index("uq_notification_templates_system_key_locale_version", table_name="notification_templates")
    op.drop_index("uq_notification_templates_tenant_key_locale_version", table_name="notification_templates")
    op.drop_index("ix_notification_templates_tenant_category", table_name="notification_templates")
    op.drop_index("ix_notification_templates_tenant_id", table_name="notification_templates")
    op.drop_table("notification_templates")

    op.drop_table("notification_categories")

    op.drop_column("lessons", "homework_text")
    op.drop_column("lessons", "has_homework")


def _category(
    key: str,
    display_name: str,
    *,
    priority: str = "normal",
    counts_towards_daily_cap: bool = True,
    can_bypass_quiet_hours: bool = False,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "key": key,
        "display_name": display_name,
        "description": None,
        "system": True,
        "default_priority": priority,
        "default_counts_towards_daily_cap": counts_towards_daily_cap,
        "default_can_bypass_quiet_hours": can_bypass_quiet_hours,
        "created_at": now,
        "updated_at": now,
    }


def _seed_system_templates() -> None:
    for template in (
        _template_seed(
            category_key="lesson_confirmation",
            key="lesson_confirmation_day_before_ru",
            name="Подтверждение урока за день",
            description="Системный шаблон для подтверждения урока за день.",
            body="Привет, {student_name}! Напоминаю, у тебя завтра занятие {lesson_datetime}. Всё в силе?",
        ),
        _template_seed(
            category_key="lesson_confirmation",
            key="lesson_confirmation_with_homework_ru",
            name="Подтверждение урока + домашка",
            description="Комбинированный шаблон для подтверждения урока и напоминания о домашке.",
            body=(
                "Привет, {student_name}! Напоминаю, у тебя завтра занятие {lesson_datetime}. Всё в силе?\n\n"
                "И не забудь выполнить и отправить домашку как минимум за час до времени твоего урока."
            ),
        ),
        _template_seed(
            category_key="lesson_reminder",
            key="lesson_reminder_soon_ru",
            name="Напоминание перед уроком",
            description="Системный шаблон для мягкого напоминания перед уроком.",
            body="Привет, {student_name}! Напоминаю о занятии {lesson_datetime}.",
        ),
        _template_seed(
            category_key="homework",
            key="homework_before_lesson_ru",
            name="Домашка к уроку",
            description="Системный шаблон для напоминания о домашке к ближайшему уроку.",
            body=(
                "Привет, {student_name}! Напоминаю: урок {lesson_datetime}. "
                "Не забудь выполнить и отправить домашку как минимум за час до времени твоего урока."
            ),
        ),
        _template_seed(
            category_key="package_renewal",
            key="package_renewal_ru",
            name="Продление пакета",
            description="Системный шаблон для напоминания о продлении пакета.",
            body=(
                "Привет, {student_name}! Твой пакет занятий заканчивается {package_end}. "
                "Скажи, пожалуйста, ты планируешь продолжать занятия в следующем месяце?"
            ),
        ),
        _template_seed(
            category_key="custom",
            key="custom_note_ru",
            name="Произвольное уведомление",
            description="Базовый системный шаблон для произвольной заметки учителя.",
            body="{custom_note}",
        ),
        _template_seed(
            category_key="teacher_alert",
            key="teacher_lesson_response_ru",
            name="Ответ ученика по уроку",
            description="Системный шаблон для уведомления учителя об ответе ученика.",
            body="Ученик {student_name} ответил по уроку {lesson_datetime}: {custom_note}",
        ),
    ):
        _insert_system_template(template)


def _template_seed(
    *,
    category_key: str,
    key: str,
    name: str,
    description: str,
    body: str,
) -> dict:
    return {
        "category_key": category_key,
        "key": key,
        "name": name,
        "description": description,
        "body": body,
    }


def _insert_system_template(template: dict) -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO notification_templates (
                tenant_id,
                category_id,
                key,
                name,
                description,
                locale,
                template_format,
                body,
                body_rich_json,
                version,
                based_on_template_id,
                system,
                archived_at,
                created_by_user_id,
                created_at,
                updated_at
            )
            SELECT
                NULL,
                notification_categories.id,
                {_sql_literal(template["key"])},
                {_sql_literal(template["name"])},
                {_sql_literal(template["description"])},
                'ru',
                'plain_text',
                {_sql_literal(template["body"])},
                NULL,
                1,
                NULL,
                TRUE,
                NULL,
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM notification_categories
            WHERE notification_categories.key = {_sql_literal(template["category_key"])}
            ON CONFLICT DO NOTHING
            """
        )
    )


def _seed_recommended_draft_rules() -> None:
    preset_keys = []
    for rule in (
        _recommended_rule_seed(
            preset_key="lesson_confirmation_day_before",
            category_key="lesson_confirmation",
            template_key="lesson_confirmation_day_before_ru",
            name="Подтверждение урока за день",
            description="Рекомендованный черновик: спросить ученика за день до урока.",
            event_type="lesson",
            trigger_type="day_offset_at_time",
            trigger_config={"days": -1, "local_time": "10:00", "event_field": "starts_at"},
            combine_policy_key="lesson_confirmation_homework",
        ),
        _recommended_rule_seed(
            preset_key="homework_before_lesson",
            category_key="homework",
            template_key="homework_before_lesson_ru",
            name="Домашка к уроку",
            description="Рекомендованный черновик: напомнить о домашке за день до урока.",
            event_type="lesson",
            trigger_type="day_offset_at_time",
            trigger_config={"days": -1, "local_time": "10:00", "event_field": "starts_at"},
            combine_policy_key="lesson_confirmation_homework",
        ),
        _recommended_rule_seed(
            preset_key="lesson_reminder_soon",
            category_key="lesson_reminder",
            template_key="lesson_reminder_soon_ru",
            name="Напоминание перед уроком",
            description="Рекомендованный черновик: мягкое напоминание за час до урока.",
            event_type="lesson",
            trigger_type="relative_offset",
            trigger_config={"minutes": -60, "event_field": "starts_at"},
        ),
        _recommended_rule_seed(
            preset_key="package_renewal",
            category_key="package_renewal",
            template_key="package_renewal_ru",
            name="Продление пакета",
            description="Рекомендованный черновик: напомнить о продлении пакета за 14 дней.",
            event_type="package",
            trigger_type="day_offset_at_time",
            trigger_config={"days": -14, "local_time": "10:00", "event_field": "starts_at"},
        ),
    ):
        preset_keys.append(rule["preset_key"])
        _insert_recommended_rule(rule)
    _insert_recommended_rule_assignments(tuple(preset_keys))


def _recommended_rule_seed(
    *,
    preset_key: str,
    category_key: str,
    template_key: str,
    name: str,
    description: str,
    event_type: str,
    trigger_type: str,
    trigger_config: dict,
    combine_policy_key: str | None = None,
) -> dict:
    return {
        "preset_key": preset_key,
        "category_key": category_key,
        "template_key": template_key,
        "name": name,
        "description": description,
        "event_type": event_type,
        "trigger_type": trigger_type,
        "trigger_config": trigger_config,
        "combine_policy_key": combine_policy_key,
    }


def _insert_recommended_rule(rule: dict) -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO notification_rules_v2 (
                tenant_id,
                preset_key,
                category_id,
                template_id,
                inline_template_body,
                inline_template_format,
                name,
                description,
                event_type,
                trigger_type,
                trigger_config,
                priority,
                status,
                combine_policy_key,
                delivery_channel,
                cap_mode,
                quiet_hours_mode,
                bypass_quiet_hours,
                created_by_user_id,
                activated_at,
                paused_at,
                archived_at,
                created_at,
                updated_at
            )
            SELECT
                tenants.id,
                {_sql_literal(rule["preset_key"])},
                notification_categories.id,
                notification_templates.id,
                NULL,
                'plain_text',
                {_sql_literal(rule["name"])},
                {_sql_literal(rule["description"])},
                {_sql_literal(rule["event_type"])},
                {_sql_literal(rule["trigger_type"])},
                {_json_literal(rule["trigger_config"])},
                'normal',
                'draft',
                {_sql_literal(rule["combine_policy_key"])},
                'telegram',
                'warn_only',
                'shift',
                FALSE,
                NULL,
                NULL,
                NULL,
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM tenants
            JOIN notification_categories
                ON notification_categories.key = {_sql_literal(rule["category_key"])}
            JOIN notification_templates
                ON notification_templates.key = {_sql_literal(rule["template_key"])}
                AND notification_templates.tenant_id IS NULL
                AND notification_templates.locale = 'ru'
                AND notification_templates.version = 1
            WHERE tenants.is_active IS TRUE
            ON CONFLICT DO NOTHING
            """
        )
    )


def _insert_recommended_rule_assignments(preset_keys: tuple[str, ...]) -> None:
    if not preset_keys:
        return
    preset_key_list = ", ".join(_sql_literal(preset_key) for preset_key in preset_keys)
    op.execute(
        sa.text(
            f"""
            INSERT INTO notification_assignments (
                tenant_id,
                rule_id,
                scope_type,
                scope_id,
                is_exclusion,
                created_at,
                updated_at
            )
            SELECT
                notification_rules_v2.tenant_id,
                notification_rules_v2.id,
                'all_learners',
                NULL,
                FALSE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM notification_rules_v2
            WHERE notification_rules_v2.preset_key IN ({preset_key_list})
            ON CONFLICT DO NOTHING
            """
        )
    )


def _json_literal(value: dict) -> str:
    return f"{_sql_literal(json.dumps(value, ensure_ascii=False))}::json"


def _sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    if "$nt$" not in value:
        return f"$nt${value}$nt$"
    return "'" + value.replace("'", "''") + "'"
