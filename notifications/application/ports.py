from __future__ import annotations

from typing import Protocol

from notifications.application.dto import (
    AudienceSelector,
    ClaimDueNotificationsResult,
    ClaimedNotificationInstance,
    DeliverySendResult,
    InstanceUpsertResult,
    LearnerGroupDraft,
    LearnerGroupRecord,
    LearnerGroupUpdateDraft,
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationAuditLogDraft,
    NotificationAuditLogRecord,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationInstanceDraft,
    NotificationInstanceRecord,
    NotificationActivityRecord,
    NotificationResponseDraft,
    NotificationResponseRecord,
    NotificationRuleCreateDraft,
    NotificationRuleDraft,
    NotificationRuleRecord,
    NotificationRuleUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
    NotificationTemplateDraft,
    NotificationTemplateRecord,
    NotificationTemplateUpdateDraft,
    PreviewEvent,
    PreviewRecipient,
    RenderedNotification,
)
from notifications.domain.entities import NotificationPreference
from notifications.domain.enums import EventType


class AudienceResolver(Protocol):
    async def resolve_recipients(
        self,
        assignments: tuple[AudienceSelector, ...],
    ) -> tuple[PreviewRecipient, ...]:
        ...


class EventRepository(Protocol):
    async def list_events_for_recipients(
        self,
        *,
        event_type: EventType,
        learner_ids: tuple[int, ...],
        horizon_days: int,
        limit: int,
    ) -> tuple[PreviewEvent, ...]:
        ...

    async def get_event(self, *, event_type: EventType, event_id: int) -> PreviewEvent | None:
        ...


class PreferenceRepository(Protocol):
    async def get_global_preference(self) -> NotificationPreference | None:
        ...

    async def get_group_preferences_for_learner(self, learner_id: int) -> tuple[NotificationPreference, ...]:
        ...

    async def get_learner_preference(self, learner_id: int) -> NotificationPreference | None:
        ...


class NotificationPreviewUnitOfWork(Protocol):
    audience_resolver: AudienceResolver
    events: EventRepository
    preferences: PreferenceRepository


class NotificationInstanceRepository(Protocol):
    async def upsert_planned_instances(
        self,
        instances: tuple[NotificationInstanceDraft, ...],
    ) -> InstanceUpsertResult:
        ...

    async def list_instances(
        self,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
        learner_id: int | None = None,
        event_type: EventType | None = None,
        scheduled_from=None,
        scheduled_to=None,
        limit: int = 100,
    ) -> tuple[NotificationInstanceRecord, ...]:
        ...

    async def get_instance(self, instance_id: int) -> NotificationInstanceRecord | None:
        ...

    async def list_activity(
        self,
        *,
        learner_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationActivityRecord, ...]:
        ...

    async def cancel_instance(
        self,
        instance_id: int,
        *,
        reason: str | None = None,
    ) -> NotificationInstanceRecord | None:
        ...

    async def schedule_instance_now(
        self,
        instance_id: int,
        *,
        now,
    ) -> NotificationInstanceRecord | None:
        ...

    async def cancel_future_instances_for_event(
        self,
        *,
        event_type: EventType,
        event_id: int,
        reason: str,
    ) -> int:
        ...

    async def cancel_future_instances_for_rules_and_learners(
        self,
        *,
        rule_ids: tuple[int, ...],
        learner_ids: tuple[int, ...],
        reason: str,
    ) -> int:
        ...

    async def cancel_future_instances_for_learners(
        self,
        *,
        learner_ids: tuple[int, ...],
        reason: str,
    ) -> int:
        ...

    async def cancel_future_instances_for_rules(
        self,
        *,
        rule_ids: tuple[int, ...],
        reason: str,
    ) -> int:
        ...

    async def claim_due_instances(
        self,
        *,
        now,
        limit: int,
        lease_seconds: int,
    ) -> ClaimDueNotificationsResult:
        ...

    async def mark_delivery_sent(
        self,
        *,
        instance_id: int,
        attempt_id: int,
        rendered: RenderedNotification,
        send_result: DeliverySendResult,
    ) -> None:
        ...

    async def mark_delivery_failed(
        self,
        *,
        instance_id: int,
        attempt_id: int,
        error_code: str,
        error_message: str,
        retryable: bool,
        failed_at,
    ) -> None:
        ...


class NotificationRenderer(Protocol):
    async def render(self, instance: ClaimedNotificationInstance) -> RenderedNotification:
        ...


class NotificationChannelAdapter(Protocol):
    async def send(
        self,
        *,
        instance: ClaimedNotificationInstance,
        rendered: RenderedNotification,
    ) -> DeliverySendResult:
        ...


class NotificationRuleRepository(Protocol):
    async def list_active_rules(self) -> tuple[NotificationRuleDraft, ...]:
        ...

    async def list_active_rules_for_group(self, group_id: int) -> tuple[NotificationRuleDraft, ...]:
        ...

    async def list_rules(self, *, include_archived: bool = False) -> tuple[NotificationRuleRecord, ...]:
        ...

    async def get_rule(self, rule_id: int) -> NotificationRuleRecord | None:
        ...

    async def create_rule(self, draft: NotificationRuleCreateDraft) -> NotificationRuleRecord:
        ...

    async def update_rule(
        self,
        rule_id: int,
        draft: NotificationRuleUpdateDraft,
    ) -> NotificationRuleRecord | None:
        ...

    async def set_rule_status(self, rule_id: int, status: str) -> NotificationRuleRecord | None:
        ...


class NotificationJobRepository(Protocol):
    async def create_job(self, draft: NotificationJobDraft) -> NotificationJobRecord:
        ...

    async def claim_queued_jobs(
        self,
        *,
        job_type: str,
        limit: int,
    ) -> tuple[NotificationJobRecord, ...]:
        ...

    async def mark_running(self, job_id: int) -> NotificationJobRecord:
        ...

    async def mark_succeeded(
        self,
        job_id: int,
        *,
        result_summary: dict,
    ) -> NotificationJobRecord:
        ...

    async def mark_failed(
        self,
        job_id: int,
        *,
        error: str,
    ) -> NotificationJobRecord:
        ...


class NotificationResponseRepository(Protocol):
    async def record_response(self, draft: NotificationResponseDraft) -> NotificationResponseRecord:
        ...


class NotificationAuditLogRepository(Protocol):
    async def record_audit(self, draft: NotificationAuditLogDraft) -> NotificationAuditLogRecord:
        ...

    async def list_audit(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationAuditLogRecord, ...]:
        ...


class LearnerGroupRepository(Protocol):
    async def list_groups(self) -> tuple[LearnerGroupRecord, ...]:
        ...

    async def get_group(self, group_id: int) -> LearnerGroupRecord | None:
        ...

    async def create_group(self, draft: LearnerGroupDraft) -> LearnerGroupRecord:
        ...

    async def update_group(self, group_id: int, draft: LearnerGroupUpdateDraft) -> LearnerGroupRecord | None:
        ...

    async def add_members(self, group_id: int, learner_ids: tuple[int, ...]) -> LearnerGroupRecord | None:
        ...

    async def deactivate_member(self, group_id: int, learner_id: int) -> LearnerGroupRecord | None:
        ...


class NotificationTemplateRepository(Protocol):
    async def list_templates(self, *, include_archived: bool = False) -> tuple[NotificationTemplateRecord, ...]:
        ...

    async def get_template(self, template_id: int) -> NotificationTemplateRecord | None:
        ...

    async def create_template(self, draft: NotificationTemplateDraft) -> NotificationTemplateRecord:
        ...

    async def create_template_version(
        self,
        template_id: int,
        draft: NotificationTemplateUpdateDraft,
    ) -> NotificationTemplateRecord | None:
        ...

    async def archive_template(self, template_id: int) -> NotificationTemplateRecord | None:
        ...


class NotificationSettingsRepository(Protocol):
    async def get_settings(self) -> NotificationSettingsRecord:
        ...

    async def update_settings(self, draft: NotificationSettingsUpdateDraft) -> NotificationSettingsRecord:
        ...

    async def list_learner_modes(self) -> tuple[LearnerNotificationModeRecord, ...]:
        ...

    async def get_learner_mode(self, learner_id: int) -> LearnerNotificationModeRecord | None:
        ...

    async def set_learner_mode(
        self,
        learner_id: int,
        draft: LearnerNotificationModeUpdateDraft,
    ) -> LearnerNotificationModeRecord | None:
        ...


class NotificationMaterializationUnitOfWork(NotificationPreviewUnitOfWork, Protocol):
    rules: NotificationRuleRepository
    instances: NotificationInstanceRepository
    jobs: NotificationJobRepository
    responses: NotificationResponseRepository
    audit_log: NotificationAuditLogRepository
    groups: LearnerGroupRepository
    templates: NotificationTemplateRepository
    settings: NotificationSettingsRepository

    async def commit(self) -> None:
        ...
