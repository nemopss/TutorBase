from __future__ import annotations

from database.models import Base, _utc_now
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


class NotificationCategory(Base):
    __tablename__ = "notification_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    description = Column(Text)
    system = Column(Boolean, nullable=False, default=True)
    default_priority = Column(String(16), nullable=False, default="normal")
    default_counts_towards_daily_cap = Column(Boolean, nullable=False, default=True)
    default_can_bypass_quiet_hours = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    templates = relationship("NotificationTemplate", back_populates="category")
    rules = relationship("NotificationRule", back_populates="category")
    instances = relationship("NotificationInstance", back_populates="category")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("notification_categories.id", ondelete="RESTRICT"), nullable=False)
    key = Column(String(128), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    locale = Column(String(16), nullable=False, default="ru")
    template_format = Column(String(32), nullable=False, default="plain_text")
    body = Column(Text, nullable=False)
    body_rich_json = Column(JSON)
    version = Column(Integer, nullable=False, default=1)
    based_on_template_id = Column(Integer, ForeignKey("notification_templates.id", ondelete="SET NULL"))
    system = Column(Boolean, nullable=False, default=False)
    archived_at = Column(DateTime(timezone=True))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    category = relationship("NotificationCategory", back_populates="templates")
    based_on_template = relationship("NotificationTemplate", remote_side=[id])
    rules = relationship("NotificationRule", back_populates="template")

    __table_args__ = (
        Index(
            "uq_notification_templates_tenant_key_locale_version",
            "tenant_id",
            "key",
            "locale",
            "version",
            unique=True,
            postgresql_where=tenant_id.is_not(None),
        ),
        Index(
            "uq_notification_templates_system_key_locale_version",
            "key",
            "locale",
            "version",
            unique=True,
            postgresql_where=tenant_id.is_(None),
        ),
        Index("ix_notification_templates_tenant_category", "tenant_id", "category_id"),
    )


class NotificationRule(Base):
    __tablename__ = "notification_rules_v2"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    preset_key = Column(String(128))
    category_id = Column(Integer, ForeignKey("notification_categories.id", ondelete="RESTRICT"), nullable=False)
    template_id = Column(Integer, ForeignKey("notification_templates.id", ondelete="SET NULL"))
    inline_template_body = Column(Text)
    inline_template_format = Column(String(32), nullable=False, default="plain_text")
    name = Column(String, nullable=False)
    description = Column(Text)
    event_type = Column(String(32), nullable=False)
    trigger_type = Column(String(32), nullable=False)
    trigger_config = Column(JSON, nullable=False, default=dict)
    priority = Column(String(16), nullable=False, default="normal")
    status = Column(String(32), nullable=False, default="draft")
    combine_policy_key = Column(String(64))
    delivery_channel = Column(String(32), nullable=False, default="telegram")
    cap_mode = Column(String(32), nullable=False, default="warn_only")
    quiet_hours_mode = Column(String(32), nullable=False, default="shift")
    bypass_quiet_hours = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    activated_at = Column(DateTime(timezone=True))
    paused_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    category = relationship("NotificationCategory", back_populates="rules")
    template = relationship("NotificationTemplate", back_populates="rules")
    assignments = relationship("NotificationAssignment", back_populates="rule", cascade="all, delete-orphan")
    instances = relationship("NotificationInstance", back_populates="rule")

    __table_args__ = (
        Index("ix_notification_rules_tenant_status", "tenant_id", "status"),
        Index("ix_notification_rules_tenant_event", "tenant_id", "event_type"),
        Index(
            "uq_notification_rules_tenant_preset_key",
            "tenant_id",
            "preset_key",
            unique=True,
            postgresql_where=preset_key.is_not(None),
        ),
    )


class NotificationAssignment(Base):
    __tablename__ = "notification_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("notification_rules_v2.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(32), nullable=False)
    scope_id = Column(Integer)
    is_exclusion = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    rule = relationship("NotificationRule", back_populates="assignments")

    __table_args__ = (
        Index(
            "uq_notification_assignments_rule_scope_with_id",
            "rule_id",
            "scope_type",
            "scope_id",
            "is_exclusion",
            unique=True,
            postgresql_where=scope_id.is_not(None),
        ),
        Index(
            "uq_notification_assignments_rule_scope_without_id",
            "rule_id",
            "scope_type",
            "is_exclusion",
            unique=True,
            postgresql_where=scope_id.is_(None),
        ),
        Index("ix_notification_assignments_tenant_scope", "tenant_id", "scope_type", "scope_id"),
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    scope_type = Column(String(32), nullable=False)
    scope_id = Column(Integer)
    notifications_enabled = Column(Boolean)
    quiet_hours_start = Column(String(5))
    quiet_hours_end = Column(String(5))
    timezone = Column(String(64))
    daily_cap = Column(Integer)
    cap_mode = Column(String(32))
    category_preferences = Column(JSON, nullable=False, default=dict)
    set_by = Column(String(32), nullable=False, default="teacher")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_notification_preferences_tenant_scope", "tenant_id", "scope_type", "scope_id"),
        Index(
            "uq_notification_preferences_global",
            "tenant_id",
            "scope_type",
            unique=True,
            postgresql_where=scope_id.is_(None),
        ),
        Index(
            "uq_notification_preferences_scoped",
            "tenant_id",
            "scope_type",
            "scope_id",
            unique=True,
            postgresql_where=scope_id.is_not(None),
        ),
    )


class NotificationJob(Base):
    __tablename__ = "notification_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    dedupe_key = Column(String(255))
    scope = Column(JSON, nullable=False, default=dict)
    attempt_count = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result_summary = Column(JSON)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    created_instances = relationship("NotificationInstance", back_populates="created_by_job")

    __table_args__ = (
        Index("ix_notification_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_notification_jobs_type_status", "job_type", "status"),
        Index("ix_notification_jobs_tenant_available", "tenant_id", "status", "available_at"),
        Index(
            "uq_notification_jobs_active_dedupe",
            "tenant_id",
            "dedupe_key",
            unique=True,
            postgresql_where=(
                dedupe_key.is_not(None)
                & (status == "queued")
            ),
        ),
    )


class NotificationInstance(Base):
    __tablename__ = "notification_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("notification_rules_v2.id", ondelete="SET NULL"))
    category_id = Column(Integer, ForeignKey("notification_categories.id", ondelete="RESTRICT"), nullable=False)
    event_type = Column(String(32), nullable=False)
    event_id = Column(Integer)
    event_key = Column(String(128), nullable=False)
    recipient_type = Column(String(32), nullable=False, default="learner")
    recipient_id = Column(Integer, nullable=False)
    learner_id = Column(Integer, ForeignKey("learners.id", ondelete="SET NULL"))
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    effective_scheduled_for = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default="scheduled")
    status_reason = Column(String(128))
    delivery_enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(String(16), nullable=False, default="normal")
    channel = Column(String(32), nullable=False, default="telegram")
    dedupe_key = Column(String(255), nullable=False)
    combination_key = Column(String(128))
    manual_overrides = Column(JSON, nullable=False, default=dict)
    explanation = Column(JSON, nullable=False, default=dict)
    processing_started_at = Column(DateTime(timezone=True))
    processing_expires_at = Column(DateTime(timezone=True))
    created_by_job_id = Column(Integer, ForeignKey("notification_jobs.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    rule = relationship("NotificationRule", back_populates="instances")
    category = relationship("NotificationCategory", back_populates="instances")
    components = relationship("NotificationInstanceComponent", back_populates="instance", cascade="all, delete-orphan")
    attempts = relationship("NotificationDeliveryAttempt", back_populates="instance", cascade="all, delete-orphan")
    responses = relationship("NotificationResponse", back_populates="instance")
    created_by_job = relationship("NotificationJob", back_populates="created_instances")

    __table_args__ = (
        Index("ix_notification_instances_due", "status", "delivery_enabled", "effective_scheduled_for"),
        Index("ix_notification_instances_tenant_recipient", "tenant_id", "recipient_type", "recipient_id"),
        Index("ix_notification_instances_tenant_event", "tenant_id", "event_type", "event_key"),
        Index(
            "uq_notification_instances_dedupe",
            "tenant_id",
            "recipient_type",
            "recipient_id",
            "event_type",
            "event_key",
            "dedupe_key",
            unique=True,
        ),
    )


class NotificationInstanceComponent(Base):
    __tablename__ = "notification_instance_components"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(Integer, ForeignKey("notification_instances.id", ondelete="CASCADE"), nullable=False)
    rule_id = Column(Integer, ForeignKey("notification_rules_v2.id", ondelete="SET NULL"))
    category_id = Column(Integer, ForeignKey("notification_categories.id", ondelete="RESTRICT"), nullable=False)
    template_id = Column(Integer, ForeignKey("notification_templates.id", ondelete="SET NULL"))
    component_key = Column(String(128), nullable=False)
    component_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    instance = relationship("NotificationInstance", back_populates="components")
    rule = relationship("NotificationRule")
    category = relationship("NotificationCategory")
    template = relationship("NotificationTemplate")

    __table_args__ = (Index("ix_notification_components_instance", "instance_id"),)


class NotificationDeliveryAttempt(Base):
    __tablename__ = "notification_delivery_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_instance_id = Column(Integer, ForeignKey("notification_instances.id", ondelete="CASCADE"), nullable=False)
    attempt_no = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    channel = Column(String(32), nullable=False, default="telegram")
    provider = Column(String(32), nullable=False, default="telegram")
    provider_chat_id = Column(String)
    provider_message_id = Column(String)
    rendered_text = Column(Text)
    reply_markup_snapshot = Column(JSON)
    error_code = Column(String(128))
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    sent_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    instance = relationship("NotificationInstance", back_populates="attempts")

    __table_args__ = (
        UniqueConstraint("notification_instance_id", "attempt_no", name="uq_notification_attempt_instance_no"),
        Index("ix_notification_attempts_tenant_status", "tenant_id", "status"),
    )


class NotificationResponse(Base):
    __tablename__ = "notification_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_instance_id = Column(Integer, ForeignKey("notification_instances.id", ondelete="SET NULL"))
    event_type = Column(String(32), nullable=False)
    event_id = Column(Integer)
    recipient_type = Column(String(32), nullable=False)
    recipient_id = Column(Integer, nullable=False)
    learner_id = Column(Integer, ForeignKey("learners.id", ondelete="SET NULL"))
    action_key = Column(String(64), nullable=False)
    response_value = Column(String(64), nullable=False)
    response_text = Column(Text)
    response_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    instance = relationship("NotificationInstance", back_populates="responses")

    __table_args__ = (
        UniqueConstraint("notification_instance_id", name="uq_notification_response_instance"),
        Index("ix_notification_responses_tenant_event", "tenant_id", "event_type", "event_id"),
        Index("ix_notification_responses_tenant_learner", "tenant_id", "learner_id"),
    )


class LessonParticipantState(Base):
    __tablename__ = "lesson_participant_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(Integer, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)
    response_state = Column(String(32), nullable=False, default="unknown")
    response_source = Column(String(64), nullable=False, default="system")
    response_at = Column(DateTime(timezone=True))
    decline_reason = Column(Text)
    last_notification_instance_id = Column(Integer, ForeignKey("notification_instances.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    last_notification_instance = relationship("NotificationInstance")

    __table_args__ = (
        UniqueConstraint("lesson_id", "learner_id", name="uq_lesson_participant_state_lesson_learner"),
        Index("ix_lesson_participant_states_tenant_lesson", "tenant_id", "lesson_id"),
        Index("ix_lesson_participant_states_tenant_learner", "tenant_id", "learner_id"),
    )


class NotificationAuditLog(Base):
    __tablename__ = "notification_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_type = Column(String(32), nullable=False)
    actor_id = Column(Integer)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer)
    action = Column(String(64), nullable=False)
    before = Column(JSON)
    after = Column(JSON)
    reason = Column(Text)
    audit_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_notification_audit_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_notification_audit_tenant_created", "tenant_id", "created_at"),
    )


class NotificationSystemSetting(Base):
    __tablename__ = "notification_system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    mode = Column(String(32), nullable=False, default="legacy")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)


class LearnerNotificationMode(Base):
    __tablename__ = "learner_notification_modes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = Column(Integer, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, unique=True)
    mode_override = Column(String(32), nullable=False, default="inherit")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    __table_args__ = (Index("ix_learner_notification_modes_tenant_learner", "tenant_id", "learner_id"),)


class LearnerGroup(Base):
    __tablename__ = "learner_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    color = Column(String(32))
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        Index("uq_learner_groups_tenant_name", "tenant_id", "name", unique=True),
        Index("ix_learner_groups_tenant_status", "tenant_id", "status"),
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("learner_groups.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(Integer, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    joined_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    left_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    group = relationship("LearnerGroup", back_populates="members")

    __table_args__ = (
        Index("ix_group_members_tenant_group", "tenant_id", "group_id"),
        Index("ix_group_members_tenant_learner", "tenant_id", "learner_id"),
        Index(
            "uq_group_members_active_membership",
            "group_id",
            "learner_id",
            unique=True,
            postgresql_where=status == "active",
        ),
    )
