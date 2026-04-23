from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from api.schemas.base import BaseRequest, BaseResponse
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


class NotificationAudienceSelectorRequest(BaseRequest):
    scope_type: str = Field(..., description="Audience scope: learner, group, package, all_learners")
    scope_id: int | None = Field(None, description="Scope id where applicable")
    is_exclusion: bool = Field(False, description="Whether this selector excludes the scope")


class NotificationRuleDraftRequest(BaseRequest):
    rule_id: int | str = Field(..., description="Persisted rule id or preview-only id")
    name: str = Field(..., min_length=1, max_length=255)
    category: CategoryKey
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    template_body: str | None = Field(None, max_length=4000)
    template_key: str | None = Field(None, max_length=128)
    combine_policy_key: str | None = Field(None, max_length=64)
    assignments: list[NotificationAudienceSelectorRequest] = Field(default_factory=list)


class NotificationRuleCreateRequest(BaseRequest):
    category: CategoryKey
    name: str = Field(..., min_length=1, max_length=255)
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    template_id: int | None = None
    inline_template_body: str | None = Field(None, max_length=4000)
    inline_template_format: str = Field("plain_text", pattern="^(plain_text|rich_text_json)$")
    description: str | None = Field(None, max_length=2000)
    priority: Priority = Priority.NORMAL
    status: RuleStatus = RuleStatus.DRAFT
    combine_policy_key: str | None = Field(None, max_length=64)
    delivery_channel: str = Field("telegram", pattern="^telegram$")
    cap_mode: CapMode = CapMode.WARN_ONLY
    quiet_hours_mode: QuietHoursMode = QuietHoursMode.SHIFT
    bypass_quiet_hours: bool = False
    assignments: list[NotificationAudienceSelectorRequest] = Field(default_factory=list)


class NotificationRuleUpdateRequest(BaseRequest):
    category: CategoryKey | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    event_type: EventType | None = None
    trigger_type: TriggerType | None = None
    trigger_config: dict[str, Any] | None = None
    template_id: int | None = None
    inline_template_body: str | None = Field(None, max_length=4000)
    inline_template_format: str | None = Field(None, pattern="^(plain_text|rich_text_json)$")
    description: str | None = Field(None, max_length=2000)
    priority: Priority | None = None
    status: RuleStatus | None = None
    combine_policy_key: str | None = Field(None, max_length=64)
    delivery_channel: str | None = Field(None, pattern="^telegram$")
    cap_mode: CapMode | None = None
    quiet_hours_mode: QuietHoursMode | None = None
    bypass_quiet_hours: bool | None = None
    assignments: list[NotificationAudienceSelectorRequest] | None = None


class NotificationRuleAssignmentResponse(BaseResponse):
    scope_type: str
    scope_id: int | None = None
    is_exclusion: bool


class NotificationRuleResponse(BaseResponse):
    id: int
    tenant_id: int
    preset_key: str | None = None
    category: CategoryKey
    template_id: int | None = None
    template_key: str | None = None
    inline_template_body: str | None = None
    inline_template_format: str
    name: str
    description: str | None = None
    event_type: EventType
    trigger_type: TriggerType
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    priority: Priority
    status: RuleStatus
    combine_policy_key: str | None = None
    delivery_channel: str
    cap_mode: CapMode
    quiet_hours_mode: QuietHoursMode
    bypass_quiet_hours: bool
    assignments: list[NotificationRuleAssignmentResponse] = Field(default_factory=list)
    created_by_user_id: int | None = None
    activated_at: datetime | None = None
    paused_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationRulesPreviewRequest(BaseRequest):
    rules: list[NotificationRuleDraftRequest] = Field(..., min_length=1, max_length=50)
    horizon_days: int = Field(30, ge=1, le=365)
    limit: int = Field(20, ge=1, le=500)


class NotificationRulePreviewRequest(BaseRequest):
    rule: NotificationRuleDraftRequest
    horizon_days: int = Field(30, ge=1, le=365)
    limit: int = Field(20, ge=1, le=500)


class NotificationPreviewComponentResponse(BaseResponse):
    rule_id: int | str
    category: CategoryKey
    scheduled_for: datetime
    effective_scheduled_for: datetime
    warnings: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)


class NotificationPreviewInstanceResponse(BaseResponse):
    kind: str
    rule_id: int | str | None = None
    learner_id: int
    event_type: EventType
    event_id: int | None
    category: CategoryKey | None = None
    scheduled_for: datetime
    effective_scheduled_for: datetime
    priority: Priority
    status: str
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    combination_key: str | None = None
    components: list[NotificationPreviewComponentResponse] = Field(default_factory=list)


class NotificationPreviewResponse(BaseResponse):
    instances: list[NotificationPreviewInstanceResponse]
    warnings: list[str] = Field(default_factory=list)


class MaterializeActiveRulesRequest(BaseRequest):
    horizon_days: int = Field(30, ge=1, le=365)
    limit: int = Field(100, ge=1, le=1000)
    delivery_enabled: bool = True
    shadow: bool = False


class MaterializeActiveRulesResponse(BaseResponse):
    job_id: int
    job_type: str
    job_status: str
    job_scope: dict[str, Any] = Field(default_factory=dict)
    planned_count: int
    upserted_count: int
    warnings: list[str] = Field(default_factory=list)


class NotificationTaskTriggerRequest(BaseRequest):
    limit: int = Field(20, ge=1, le=500)
    job_type: str | None = Field(None, max_length=64)


class NotificationTaskTriggerResponse(BaseResponse):
    task_id: str
    task_name: str
    tenant_id: int
    limit: int
    job_type: str | None = None
    queued: bool = True


class NotificationReconcileEventRequest(BaseRequest):
    event_type: EventType
    event_id: int = Field(..., ge=1)
    reason: str = Field("manual_reconciliation", min_length=1, max_length=128)
    delivery_enabled: bool = False
    shadow: bool = True
    horizon_days: int = Field(30, ge=1, le=365)
    limit: int = Field(100, ge=1, le=1000)


class NotificationJobResponse(BaseResponse):
    id: int
    job_type: str
    status: str
    scope: dict[str, Any] = Field(default_factory=dict)


class NotificationSettingsUpdateRequest(BaseRequest):
    mode: NotificationSystemMode | None = None
    confirm_global_new: bool = False
    notifications_enabled: bool | None = None
    quiet_hours_start: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: str | None = Field(None, max_length=64)
    daily_cap: int | None = Field(None, ge=0, le=50)
    cap_mode: CapMode | None = None
    category_preferences: dict[str, bool] | None = None


class NotificationSettingsResponse(BaseResponse):
    tenant_id: int
    mode: NotificationSystemMode
    notifications_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None
    daily_cap: int | None = None
    cap_mode: CapMode | None = None
    category_preferences: dict[str, bool] = Field(default_factory=dict)
    updated_at: datetime | None = None


class LearnerNotificationModeUpdateRequest(BaseRequest):
    mode_override: NotificationSystemMode


class LearnerNotificationModeResponse(BaseResponse):
    learner_id: int
    display_name: str
    mode_override: NotificationSystemMode
    effective_mode: NotificationSystemMode
    updated_at: datetime | None = None


class NotificationTemplateCreateRequest(BaseRequest):
    category: CategoryKey
    key: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=4000)
    description: str | None = Field(None, max_length=2000)
    locale: str = Field("ru", max_length=16)
    template_format: str = Field("plain_text", pattern="^(plain_text|rich_text_json)$")


class NotificationTemplateUpdateRequest(BaseRequest):
    category: CategoryKey | None = None
    key: str | None = Field(None, min_length=1, max_length=128)
    name: str | None = Field(None, min_length=1, max_length=255)
    body: str | None = Field(None, min_length=1, max_length=4000)
    description: str | None = Field(None, max_length=2000)
    locale: str | None = Field(None, max_length=16)
    template_format: str | None = Field(None, pattern="^(plain_text|rich_text_json)$")


class NotificationTemplateResponse(BaseResponse):
    id: int
    tenant_id: int | None
    category: CategoryKey
    key: str
    name: str
    body: str
    description: str | None = None
    locale: str
    template_format: str
    version: int
    system: bool
    based_on_template_id: int | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationInstanceDraftResponse(BaseResponse):
    rule_id: int | str | None
    category: CategoryKey
    event_type: EventType
    event_id: int | None
    event_key: str
    recipient_type: str
    recipient_id: int
    scheduled_for: datetime
    effective_scheduled_for: datetime
    status: InstanceStatus
    delivery_enabled: bool
    priority: Priority
    dedupe_key: str
    combination_key: str | None = None


class NotificationInstanceComponentResponse(BaseResponse):
    component_id: int
    rule_id: int | None = None
    category: CategoryKey
    template_id: int | None = None
    component_key: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationDeliveryAttemptResponse(BaseResponse):
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


class NotificationInstanceResponse(BaseResponse):
    id: int
    rule_id: int | None = None
    category: CategoryKey
    event_type: EventType
    event_id: int | None = None
    event_key: str
    recipient_type: str
    recipient_id: int
    learner_id: int | None = None
    learner_display_name: str | None = None
    scheduled_for: datetime
    effective_scheduled_for: datetime
    status: InstanceStatus
    status_reason: str | None = None
    delivery_enabled: bool
    priority: Priority
    channel: str
    dedupe_key: str
    combination_key: str | None = None
    explanation: dict[str, Any] = Field(default_factory=dict)
    components: list[NotificationInstanceComponentResponse] = Field(default_factory=list)
    latest_attempt: NotificationDeliveryAttemptResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationActivityResponse(BaseResponse):
    activity_type: str
    activity_id: int
    notification_instance_id: int | None = None
    category: CategoryKey | None = None
    event_type: EventType
    event_id: int | None = None
    learner_id: int | None = None
    learner_display_name: str | None = None
    status: str
    action_key: str | None = None
    response_value: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider_message_id: str | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationActivityAcknowledgementRequest(BaseRequest):
    activity_type: Literal["teacher_alert"]
    activity_id: int = Field(..., ge=1)


class NotificationActivityAcknowledgementResponse(BaseResponse):
    id: int
    tenant_id: int
    activity_type: Literal["teacher_alert"]
    activity_id: int
    acknowledged_by_user_id: int | None = None
    acknowledged_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationAuditLogResponse(BaseResponse):
    id: int
    actor_type: str
    actor_id: int | None = None
    entity_type: str
    entity_id: int | None = None
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class NotificationInstanceCancelRequest(BaseRequest):
    reason: str | None = Field(None, max_length=255)
