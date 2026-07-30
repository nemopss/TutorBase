from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    InstanceStatus,
    NotificationSystemMode,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
)


@dataclass(frozen=True)
class AudienceSelector:
    scope_type: str
    scope_id: int | None = None
    is_exclusion: bool = False


@dataclass(frozen=True)
class NotificationRuleDraft:
    rule_id: int | str
    name: str
    category: CategoryKey
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any]
    priority: Priority = Priority.NORMAL
    template_body: str | None = None
    template_key: str | None = None
    combine_policy_key: str | None = None
    assignments: tuple[AudienceSelector, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NotificationRuleCreateDraft:
    category: CategoryKey
    name: str
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any]
    template_id: int | None = None
    inline_template_body: str | None = None
    inline_template_format: str = "plain_text"
    description: str | None = None
    priority: Priority = Priority.NORMAL
    status: RuleStatus = RuleStatus.DRAFT
    combine_policy_key: str | None = None
    delivery_channel: str = "telegram"
    cap_mode: CapMode = CapMode.WARN_ONLY
    quiet_hours_mode: QuietHoursMode = QuietHoursMode.SHIFT
    bypass_quiet_hours: bool = False
    assignments: tuple[AudienceSelector, ...] = field(default_factory=tuple)
    created_by_user_id: int | None = None


@dataclass(frozen=True)
class NotificationRuleUpdateDraft:
    category: CategoryKey | None = None
    name: str | None = None
    event_type: EventType | None = None
    trigger_type: TriggerType | None = None
    trigger_config: dict[str, Any] | None = None
    template_id: int | None = None
    template_id_set: bool = False
    inline_template_body: str | None = None
    inline_template_body_set: bool = False
    inline_template_format: str | None = None
    description: str | None = None
    description_set: bool = False
    priority: Priority | None = None
    status: RuleStatus | None = None
    combine_policy_key: str | None = None
    combine_policy_key_set: bool = False
    delivery_channel: str | None = None
    cap_mode: CapMode | None = None
    quiet_hours_mode: QuietHoursMode | None = None
    bypass_quiet_hours: bool | None = None
    assignments: tuple[AudienceSelector, ...] | None = None


@dataclass(frozen=True)
class NotificationRuleRecord:
    rule_id: int
    tenant_id: int
    preset_key: str | None
    category: CategoryKey
    template_id: int | None
    template_key: str | None
    inline_template_body: str | None
    inline_template_format: str
    name: str
    description: str | None
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any]
    priority: Priority
    status: RuleStatus
    combine_policy_key: str | None
    delivery_channel: str
    cap_mode: CapMode
    quiet_hours_mode: QuietHoursMode
    bypass_quiet_hours: bool
    assignments: tuple[AudienceSelector, ...] = field(default_factory=tuple)
    created_by_user_id: int | None = None
    activated_at: datetime | None = None
    paused_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class PreviewRecipient:
    learner_id: int
    display_name: str
    notifications_enabled: bool = True
    has_contact: bool = True
    timezone: str = "Europe/Moscow"


@dataclass(frozen=True)
class PreviewEvent:
    event_type: EventType
    event_id: int
    learner_id: int
    starts_at: datetime | None
    ends_at: datetime | None = None
    timezone: str = "Europe/Moscow"
    package_status: str | None = None
    lesson_status: str | None = None
    has_homework: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewInstance:
    rule_id: int | str
    learner_id: int
    event_type: EventType
    event_id: int | None
    category: CategoryKey
    scheduled_for: datetime
    effective_scheduled_for: datetime
    priority: Priority
    status: str
    reason: str = "scheduled"
    warnings: tuple[str, ...] = ()
    explanation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CombinedPreviewInstance:
    combination_key: str
    learner_id: int
    event_type: EventType
    event_id: int | None
    scheduled_for: datetime
    effective_scheduled_for: datetime
    priority: Priority
    components: tuple[PreviewInstance, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RulePreviewResult:
    instances: tuple[PreviewInstance | CombinedPreviewInstance, ...]
    warnings: tuple[str, ...] = ()
    has_more: bool = False


@dataclass(frozen=True)
class NotificationInstanceComponentDraft:
    rule_id: int | str
    category: CategoryKey
    component_key: str
    template_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationInstanceDraft:
    rule_id: int | str | None
    category: CategoryKey
    event_type: EventType
    event_id: int | None
    event_key: str
    recipient_type: str
    recipient_id: int
    learner_id: int | None
    scheduled_for: datetime
    effective_scheduled_for: datetime
    status: InstanceStatus
    delivery_enabled: bool
    priority: Priority
    channel: str
    dedupe_key: str
    status_reason: str | None = None
    combination_key: str | None = None
    explanation: dict[str, Any] = field(default_factory=dict)
    components: tuple[NotificationInstanceComponentDraft, ...] = ()


@dataclass(frozen=True)
class InstanceUpsertResult:
    planned_count: int
    upserted_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True)
class MaterializeRulesResult:
    planned_instances: tuple[NotificationInstanceDraft, ...]
    upsert_result: InstanceUpsertResult
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NotificationJobDraft:
    job_type: str
    scope: dict[str, Any] = field(default_factory=dict)
    created_by_user_id: int | None = None
    dedupe_key: str | None = None


@dataclass(frozen=True)
class NotificationJobRecord:
    job_id: int
    job_type: str
    status: str
    scope: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0


@dataclass(frozen=True)
class ClaimNotificationJobsResult:
    claimed: tuple[NotificationJobRecord, ...]


@dataclass(frozen=True)
class MaterializeActiveRulesResult:
    job: NotificationJobRecord
    materialization: MaterializeRulesResult


@dataclass(frozen=True)
class ReconcileNotificationEventResult:
    job: NotificationJobRecord
    materialization: MaterializeRulesResult
    event_found: bool
    cancelled_count: int = 0


@dataclass(frozen=True)
class ReconcileNotificationGroupMembershipResult:
    job: NotificationJobRecord
    materialization: MaterializeRulesResult
    group_id: int
    learner_ids: tuple[int, ...]
    rules_count: int
    cancelled_count: int = 0


@dataclass(frozen=True)
class ClaimedNotificationInstance:
    instance_id: int
    attempt_id: int
    attempt_no: int
    rule_id: int | None
    category: CategoryKey
    event_type: EventType
    event_id: int | None
    recipient_type: str
    recipient_id: int
    learner_id: int | None
    effective_scheduled_for: datetime
    priority: Priority
    channel: str
    provider_chat_id: str | None = None
    explanation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimDueNotificationsResult:
    claimed: tuple[ClaimedNotificationInstance, ...]


@dataclass(frozen=True)
class RenderedNotification:
    text: str
    parse_mode: str | None = None
    reply_markup_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True)
class DeliverySendResult:
    provider: str
    provider_chat_id: str | None
    provider_message_id: str | None
    sent_at: datetime


@dataclass(frozen=True)
class ExecuteNotificationDeliveryResult:
    instance_id: int
    attempt_id: int
    status: InstanceStatus
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class NotificationResponseDraft:
    notification_instance_id: int
    action_key: str
    response_value: str
    response_text: str | None = None
    response_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationResponseRecord:
    response_id: int
    notification_instance_id: int
    event_type: EventType
    event_id: int | None
    learner_id: int | None
    response_value: str
    lesson_participant_state_updated: bool = False


@dataclass(frozen=True)
class LearnerGroupDraft:
    name: str
    description: str | None = None
    color: str | None = None
    learner_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class LearnerGroupUpdateDraft:
    name: str | None = None
    description: str | None = None
    color: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class LearnerGroupMemberRecord:
    learner_id: int
    display_name: str
    status: str
    joined_at: datetime | None = None
    left_at: datetime | None = None


@dataclass(frozen=True)
class LearnerGroupRecord:
    group_id: int
    name: str
    description: str | None
    color: str | None
    status: str
    member_count: int = 0
    members: tuple[LearnerGroupMemberRecord, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class NotificationTemplateDraft:
    category: CategoryKey
    key: str
    name: str
    body: str
    description: str | None = None
    locale: str = "ru"
    template_format: str = "plain_text"
    created_by_user_id: int | None = None


@dataclass(frozen=True)
class NotificationTemplateUpdateDraft:
    category: CategoryKey | None = None
    key: str | None = None
    name: str | None = None
    body: str | None = None
    description: str | None = None
    locale: str | None = None
    template_format: str | None = None
    created_by_user_id: int | None = None


@dataclass(frozen=True)
class NotificationTemplateRecord:
    template_id: int
    tenant_id: int | None
    category: CategoryKey
    key: str
    name: str
    body: str
    description: str | None
    locale: str
    template_format: str
    version: int
    system: bool
    based_on_template_id: int | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class NotificationSettingsUpdateDraft:
    mode: NotificationSystemMode | None = None
    confirm_global_new: bool = False
    notifications_enabled: bool | None = None
    notifications_enabled_set: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_start_set: bool = False
    quiet_hours_end: str | None = None
    quiet_hours_end_set: bool = False
    timezone: str | None = None
    timezone_set: bool = False
    daily_cap: int | None = None
    daily_cap_set: bool = False
    cap_mode: CapMode | None = None
    cap_mode_set: bool = False
    category_preferences: dict[str, bool] | None = None
    category_preferences_set: bool = False


@dataclass(frozen=True)
class NotificationSettingsRecord:
    tenant_id: int
    mode: NotificationSystemMode
    notifications_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    daily_cap: int | None = None
    cap_mode: CapMode | None = None
    category_preferences: dict[str, bool] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class LearnerNotificationModeUpdateDraft:
    mode_override: NotificationSystemMode


@dataclass(frozen=True)
class LearnerNotificationModeRecord:
    learner_id: int
    display_name: str
    mode_override: NotificationSystemMode
    effective_mode: NotificationSystemMode
    updated_at: datetime | None = None


@dataclass(frozen=True)
class NotificationInstanceComponentRecord:
    component_id: int
    rule_id: int | None
    category: CategoryKey
    template_id: int | None
    component_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationDeliveryAttemptRecord:
    attempt_id: int
    attempt_no: int
    status: str
    channel: str
    provider: str
    provider_chat_id: str | None = None
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    sent_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class NotificationInstanceRecord:
    instance_id: int
    rule_id: int | None
    category: CategoryKey
    event_type: EventType
    event_id: int | None
    event_key: str
    recipient_type: str
    recipient_id: int
    learner_id: int | None
    learner_display_name: str | None
    scheduled_for: datetime
    effective_scheduled_for: datetime
    status: InstanceStatus
    status_reason: str | None
    delivery_enabled: bool
    priority: Priority
    channel: str
    dedupe_key: str
    combination_key: str | None
    explanation: dict[str, Any] = field(default_factory=dict)
    components: tuple[NotificationInstanceComponentRecord, ...] = ()
    latest_attempt: NotificationDeliveryAttemptRecord | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class NotificationActivityRecord:
    activity_type: str
    activity_id: int
    notification_instance_id: int | None
    category: CategoryKey | None
    event_type: EventType
    event_id: int | None
    learner_id: int | None
    learner_display_name: str | None
    status: str
    action_key: str | None = None
    response_value: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider_message_id: str | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationAuditLogDraft:
    actor_type: str
    actor_id: int | None
    entity_type: str
    entity_id: int | None
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationAuditLogRecord:
    audit_id: int
    actor_type: str
    actor_id: int | None
    entity_type: str
    entity_id: int | None
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
