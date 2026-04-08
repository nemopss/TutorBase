from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone

from database.models import BotUser, Learner, Lesson, LessonPackage
from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.orm import aliased, joinedload, selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications.application.dto import (
    AudienceSelector,
    ClaimDueNotificationsResult,
    ClaimedNotificationInstance,
    DeliverySendResult,
    InstanceUpsertResult,
    LearnerGroupDraft,
    LearnerGroupMemberRecord,
    LearnerGroupRecord,
    LearnerGroupUpdateDraft,
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationAuditLogDraft,
    NotificationAuditLogRecord,
    NotificationActivityRecord,
    NotificationDeliveryAttemptRecord,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationInstanceComponentRecord,
    NotificationInstanceDraft,
    NotificationInstanceRecord,
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
from notifications.domain.entities import NotificationPreference as DomainNotificationPreference
from notifications.domain.entities import QuietHours
from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    InstanceStatus,
    NotificationSystemMode,
    PreferenceScope,
    Priority,
    QuietHoursMode,
    RuleStatus,
    TriggerType,
)
from notifications.infrastructure.models import (
    GroupMember,
    LearnerGroup,
    LearnerNotificationMode,
    NotificationAssignment,
    NotificationAuditLog,
    NotificationCategory,
    NotificationDeliveryAttempt,
    NotificationInstance,
    NotificationInstanceComponent,
    NotificationJob,
    NotificationPreference,
    NotificationResponse,
    NotificationRule,
    NotificationSystemSetting,
    NotificationTemplate,
    LessonParticipantState,
)


class SqlAlchemyNotificationUnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        tenant_id: int,
    ) -> None:
        self._session_factory = session_factory
        self.tenant_id = tenant_id
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> SqlAlchemyNotificationUnitOfWork:
        self.session = self._session_factory()
        _bind_repositories(self, self.session, tenant_id=self.tenant_id)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is None:
            return
        if exc_type is not None:
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Notification unit of work is not open")
        await self.session.commit()

    async def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("Notification unit of work is not open")
        await self.session.rollback()


class SqlAlchemySessionNotificationUnitOfWork:
    def __init__(self, session: AsyncSession, *, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id
        _bind_repositories(self, session, tenant_id=tenant_id)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


def _bind_repositories(target, session: AsyncSession, *, tenant_id: int) -> None:
    target.audience_resolver = SqlAlchemyAudienceResolver(
        session,
        tenant_id=tenant_id,
    )
    target.events = SqlAlchemyEventRepository(
        session,
        tenant_id=tenant_id,
    )
    target.preferences = SqlAlchemyPreferenceRepository(
        session,
        tenant_id=tenant_id,
    )
    target.rules = SqlAlchemyNotificationRuleRepository(
        session,
        tenant_id=tenant_id,
    )
    target.jobs = SqlAlchemyNotificationJobRepository(
        session,
        tenant_id=tenant_id,
    )
    target.instances = SqlAlchemyNotificationInstanceRepository(
        session,
        tenant_id=tenant_id,
    )
    target.responses = SqlAlchemyNotificationResponseRepository(
        session,
        tenant_id=tenant_id,
    )
    target.audit_log = SqlAlchemyNotificationAuditLogRepository(
        session,
        tenant_id=tenant_id,
    )
    target.groups = SqlAlchemyLearnerGroupRepository(
        session,
        tenant_id=tenant_id,
    )
    target.templates = SqlAlchemyNotificationTemplateRepository(
        session,
        tenant_id=tenant_id,
    )
    target.settings = SqlAlchemyNotificationSettingsRepository(
        session,
        tenant_id=tenant_id,
    )


class SqlAlchemyAudienceResolver:
    def __init__(self, session: AsyncSession, *, tenant_id: int) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def resolve_recipients(
        self,
        assignments: tuple[AudienceSelector, ...],
    ) -> tuple[PreviewRecipient, ...]:
        included_ids = await self._resolve_assignment_ids(
            tuple(assignment for assignment in assignments if not assignment.is_exclusion)
        )
        excluded_ids = await self._resolve_assignment_ids(
            tuple(assignment for assignment in assignments if assignment.is_exclusion)
        )
        learner_ids = tuple(sorted(included_ids - excluded_ids))
        if not learner_ids:
            return ()

        result = await self._session.execute(_learner_recipients_stmt(self._tenant_id, learner_ids))
        return tuple(_recipient_from_row(row) for row in result)

    async def _resolve_assignment_ids(self, assignments: tuple[AudienceSelector, ...]) -> set[int]:
        learner_ids: set[int] = set()
        for assignment in assignments:
            if assignment.scope_type == "all_learners":
                learner_ids.update(await self._learner_ids_for_all())
            elif assignment.scope_type == "learner" and assignment.scope_id is not None:
                learner_ids.add(assignment.scope_id)
            elif assignment.scope_type == "group" and assignment.scope_id is not None:
                learner_ids.update(await self._learner_ids_for_group(assignment.scope_id))
            elif assignment.scope_type == "package" and assignment.scope_id is not None:
                learner_id = await self._learner_id_for_package(assignment.scope_id)
                if learner_id is not None:
                    learner_ids.add(learner_id)
        return learner_ids

    async def _learner_ids_for_all(self) -> set[int]:
        result = await self._session.execute(
            select(Learner.id).where(Learner.tenant_id == self._tenant_id)
        )
        return set(result.scalars())

    async def _learner_ids_for_group(self, group_id: int) -> set[int]:
        result = await self._session.execute(
            select(GroupMember.learner_id).where(
                GroupMember.tenant_id == self._tenant_id,
                GroupMember.group_id == group_id,
                GroupMember.status == "active",
            )
        )
        return set(result.scalars())

    async def _learner_id_for_package(self, package_id: int) -> int | None:
        result = await self._session.execute(
            select(LessonPackage.learner_id).where(
                LessonPackage.tenant_id == self._tenant_id,
                LessonPackage.id == package_id,
            )
        )
        return result.scalar_one_or_none()


class SqlAlchemyEventRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def list_events_for_recipients(
        self,
        *,
        event_type: EventType,
        learner_ids: tuple[int, ...],
        horizon_days: int,
        limit: int,
    ) -> tuple[PreviewEvent, ...]:
        if not learner_ids:
            return ()
        starts_at = self._now_factory()
        ends_at = starts_at + timedelta(days=horizon_days)
        if event_type == EventType.LESSON:
            result = await self._session.execute(
                _lesson_events_stmt(
                    self._tenant_id,
                    learner_ids,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    limit=limit,
                )
            )
            return tuple(_lesson_event_from_row(row) for row in result)
        if event_type == EventType.PACKAGE:
            result = await self._session.execute(
                _package_events_stmt(
                    self._tenant_id,
                    learner_ids,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    limit=limit,
                )
            )
            return tuple(_package_event_from_row(row) for row in result)
        return ()

    async def get_event(self, *, event_type: EventType, event_id: int) -> PreviewEvent | None:
        if event_type == EventType.LESSON:
            result = await self._session.execute(_lesson_event_by_id_stmt(self._tenant_id, event_id))
            row = result.first()
            return _lesson_event_from_row(row) if row is not None else None
        if event_type == EventType.PACKAGE:
            result = await self._session.execute(_package_event_by_id_stmt(self._tenant_id, event_id))
            row = result.first()
            return _package_event_from_row(row) if row is not None else None
        return None


class SqlAlchemyPreferenceRepository:
    def __init__(self, session: AsyncSession, *, tenant_id: int) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_global_preference(self) -> DomainNotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.tenant_id == self._tenant_id,
                NotificationPreference.scope_type == PreferenceScope.GLOBAL.value,
                NotificationPreference.scope_id.is_(None),
            )
        )
        return _preference_from_model(result.scalar_one_or_none())

    async def get_group_preferences_for_learner(
        self,
        learner_id: int,
    ) -> tuple[DomainNotificationPreference, ...]:
        result = await self._session.execute(
            select(NotificationPreference)
            .join(
                GroupMember,
                (GroupMember.group_id == NotificationPreference.scope_id)
                & (GroupMember.tenant_id == NotificationPreference.tenant_id),
            )
            .where(
                NotificationPreference.tenant_id == self._tenant_id,
                NotificationPreference.scope_type == PreferenceScope.GROUP.value,
                GroupMember.learner_id == learner_id,
                GroupMember.status == "active",
            )
        )
        return tuple(
            preference
            for preference in (_preference_from_model(model) for model in result.scalars())
            if preference is not None
        )

    async def get_learner_preference(self, learner_id: int) -> DomainNotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.tenant_id == self._tenant_id,
                NotificationPreference.scope_type == PreferenceScope.LEARNER.value,
                NotificationPreference.scope_id == learner_id,
            )
        )
        return _preference_from_model(result.scalar_one_or_none())


class SqlAlchemyNotificationRuleRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def list_active_rules(self) -> tuple[NotificationRuleDraft, ...]:
        result = await self._session.execute(_active_rules_stmt(self._tenant_id))
        return tuple(map_notification_rule_to_draft(rule) for rule in result.scalars().unique())

    async def list_active_rules_for_group(self, group_id: int) -> tuple[NotificationRuleDraft, ...]:
        result = await self._session.execute(_active_rules_for_group_stmt(self._tenant_id, group_id))
        return tuple(map_notification_rule_to_draft(rule) for rule in result.scalars().unique())

    async def list_rules(self, *, include_archived: bool = False) -> tuple[NotificationRuleRecord, ...]:
        result = await self._session.execute(
            _notification_rules_stmt(self._tenant_id, include_archived=include_archived)
        )
        return tuple(map_notification_rule_to_record(rule) for rule in result.scalars().unique())

    async def get_rule(self, rule_id: int) -> NotificationRuleRecord | None:
        rule = await self._get_rule(rule_id)
        return map_notification_rule_to_record(rule) if rule is not None else None

    async def create_rule(self, draft: NotificationRuleCreateDraft) -> NotificationRuleRecord:
        self._validate_message_source(
            template_id=draft.template_id,
            inline_template_body=draft.inline_template_body,
        )
        await self._validate_template_id(draft.template_id, category=draft.category)
        now = self._now_factory()
        rule = NotificationRule(
            tenant_id=self._tenant_id,
            category_id=await self._category_id(draft.category),
            template_id=draft.template_id,
            inline_template_body=draft.inline_template_body,
            inline_template_format=draft.inline_template_format,
            name=draft.name,
            description=draft.description,
            event_type=draft.event_type.value,
            trigger_type=draft.trigger_type.value,
            trigger_config=draft.trigger_config,
            priority=draft.priority.value,
            status=draft.status.value,
            combine_policy_key=draft.combine_policy_key,
            delivery_channel=draft.delivery_channel,
            cap_mode=draft.cap_mode.value,
            quiet_hours_mode=draft.quiet_hours_mode.value,
            bypass_quiet_hours=draft.bypass_quiet_hours,
            created_by_user_id=draft.created_by_user_id,
            activated_at=now if draft.status == RuleStatus.ACTIVE else None,
            paused_at=now if draft.status == RuleStatus.PAUSED else None,
            archived_at=now if draft.status == RuleStatus.ARCHIVED else None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(rule)
        await self._session.flush()
        await self._replace_assignments(rule, draft.assignments, now=now)
        await self._session.refresh(rule, attribute_names=["category", "template", "assignments"])
        return map_notification_rule_to_record(rule)

    async def update_rule(
        self,
        rule_id: int,
        draft: NotificationRuleUpdateDraft,
    ) -> NotificationRuleRecord | None:
        rule = await self._get_rule(rule_id)
        if rule is None:
            return None

        if draft.category is not None:
            rule.category_id = await self._category_id(draft.category)
        if draft.template_id_set:
            category = draft.category or CategoryKey(rule.category.key)
            await self._validate_template_id(draft.template_id, category=category)
            rule.template_id = draft.template_id
        elif draft.category is not None and rule.template_id is not None:
            await self._validate_template_id(rule.template_id, category=draft.category)
        if draft.inline_template_body_set:
            rule.inline_template_body = draft.inline_template_body
        if draft.inline_template_format is not None:
            rule.inline_template_format = draft.inline_template_format
        if draft.name is not None:
            rule.name = draft.name
        if draft.description_set:
            rule.description = draft.description
        if draft.event_type is not None:
            rule.event_type = draft.event_type.value
        if draft.trigger_type is not None:
            rule.trigger_type = draft.trigger_type.value
        if draft.trigger_config is not None:
            rule.trigger_config = draft.trigger_config
        if draft.priority is not None:
            rule.priority = draft.priority.value
        if draft.status is not None:
            self._apply_status(rule, draft.status, now=self._now_factory())
        if draft.combine_policy_key_set:
            rule.combine_policy_key = draft.combine_policy_key
        if draft.delivery_channel is not None:
            rule.delivery_channel = draft.delivery_channel
        if draft.cap_mode is not None:
            rule.cap_mode = draft.cap_mode.value
        if draft.quiet_hours_mode is not None:
            rule.quiet_hours_mode = draft.quiet_hours_mode.value
        if draft.bypass_quiet_hours is not None:
            rule.bypass_quiet_hours = draft.bypass_quiet_hours

        now = self._now_factory()
        rule.updated_at = now
        if draft.assignments is not None:
            await self._replace_assignments(rule, draft.assignments, now=now)
        self._validate_message_source(
            template_id=rule.template_id,
            inline_template_body=rule.inline_template_body,
        )
        await self._session.flush()
        await self._session.refresh(rule, attribute_names=["category", "template", "assignments"])
        return map_notification_rule_to_record(rule)

    async def set_rule_status(self, rule_id: int, status: str) -> NotificationRuleRecord | None:
        rule = await self._get_rule(rule_id)
        if rule is None:
            return None
        now = self._now_factory()
        self._apply_status(rule, RuleStatus(status), now=now)
        rule.updated_at = now
        await self._session.flush()
        return map_notification_rule_to_record(rule)

    async def _get_rule(self, rule_id: int) -> NotificationRule | None:
        result = await self._session.execute(
            select(NotificationRule)
            .options(
                joinedload(NotificationRule.category),
                joinedload(NotificationRule.template),
                selectinload(NotificationRule.assignments),
            )
            .where(
                NotificationRule.tenant_id == self._tenant_id,
                NotificationRule.id == rule_id,
            )
        )
        return result.scalar_one_or_none()

    async def _category_id(self, category: CategoryKey) -> int:
        result = await self._session.execute(
            select(NotificationCategory.id).where(NotificationCategory.key == category.value)
        )
        category_id = result.scalar_one_or_none()
        if category_id is None:
            raise ValueError(f"Missing notification category: {category.value}")
        return category_id

    async def _validate_template_id(
        self,
        template_id: int | None,
        *,
        category: CategoryKey,
    ) -> None:
        if template_id is None:
            return
        result = await self._session.execute(
            select(NotificationTemplate)
            .options(joinedload(NotificationTemplate.category))
            .where(
                NotificationTemplate.id == template_id,
                (
                    (NotificationTemplate.tenant_id == self._tenant_id)
                    | (NotificationTemplate.tenant_id.is_(None))
                ),
                NotificationTemplate.archived_at.is_(None),
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise ValueError(f"Notification template {template_id} not found")
        if CategoryKey(template.category.key) != category:
            raise ValueError("Notification template category does not match rule category")

    def _validate_message_source(
        self,
        *,
        template_id: int | None,
        inline_template_body: str | None,
    ) -> None:
        if template_id is None and not (inline_template_body or "").strip():
            raise ValueError("Notification rule requires template_id or inline_template_body")

    async def _replace_assignments(
        self,
        rule: NotificationRule,
        assignments: tuple[AudienceSelector, ...],
        *,
        now: datetime,
    ) -> None:
        await self._session.execute(
            delete(NotificationAssignment).where(
                NotificationAssignment.tenant_id == self._tenant_id,
                NotificationAssignment.rule_id == rule.id,
            )
        )
        for assignment in assignments:
            self._session.add(
                NotificationAssignment(
                    tenant_id=self._tenant_id,
                    rule_id=rule.id,
                    scope_type=assignment.scope_type,
                    scope_id=assignment.scope_id,
                    is_exclusion=assignment.is_exclusion,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self._session.flush()

    def _apply_status(
        self,
        rule: NotificationRule,
        status: RuleStatus,
        *,
        now: datetime,
    ) -> None:
        rule.status = status.value
        if status == RuleStatus.ACTIVE:
            rule.activated_at = rule.activated_at or now
            rule.paused_at = None
        elif status == RuleStatus.PAUSED:
            rule.paused_at = now
        elif status == RuleStatus.ARCHIVED:
            rule.archived_at = rule.archived_at or now
        elif status == RuleStatus.DRAFT:
            rule.paused_at = None


class SqlAlchemyNotificationJobRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def create_job(self, draft: NotificationJobDraft) -> NotificationJobRecord:
        now = self._now_factory()
        job = NotificationJob(
            tenant_id=self._tenant_id,
            job_type=draft.job_type,
            status="queued",
            scope=draft.scope,
            created_by_user_id=draft.created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(job)
        await self._session.flush()
        return _job_record_from_model(job)

    async def claim_queued_jobs(
        self,
        *,
        job_type: str,
        limit: int,
    ) -> tuple[NotificationJobRecord, ...]:
        result = await self._session.execute(
            _queued_jobs_for_claim_stmt(
                tenant_id=self._tenant_id,
                job_type=job_type,
                limit=limit,
            )
        )
        jobs = tuple(result.scalars().all())
        now = self._now_factory()
        for job in jobs:
            job.status = "running"
            job.started_at = job.started_at or now
            job.updated_at = now
        await self._session.flush()
        return tuple(_job_record_from_model(job) for job in jobs)

    async def mark_running(self, job_id: int) -> NotificationJobRecord:
        job = await self._get_job(job_id)
        now = self._now_factory()
        job.status = "running"
        job.started_at = job.started_at or now
        job.updated_at = now
        await self._session.flush()
        return _job_record_from_model(job)

    async def mark_succeeded(
        self,
        job_id: int,
        *,
        result_summary: dict,
    ) -> NotificationJobRecord:
        job = await self._get_job(job_id)
        now = self._now_factory()
        job.status = "succeeded"
        job.finished_at = now
        job.result_summary = result_summary
        job.updated_at = now
        await self._session.flush()
        return _job_record_from_model(job)

    async def mark_failed(
        self,
        job_id: int,
        *,
        error: str,
    ) -> NotificationJobRecord:
        job = await self._get_job(job_id)
        now = self._now_factory()
        job.status = "failed"
        job.finished_at = now
        job.error = error
        job.updated_at = now
        await self._session.flush()
        return _job_record_from_model(job)

    async def _get_job(self, job_id: int) -> NotificationJob:
        job = await self._session.get(NotificationJob, job_id)
        if job is None or job.tenant_id != self._tenant_id:
            raise ValueError(f"Notification job {job_id} not found")
        return job


class SqlAlchemyNotificationInstanceRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def upsert_planned_instances(
        self,
        instances: tuple[NotificationInstanceDraft, ...],
    ) -> InstanceUpsertResult:
        if not instances:
            return InstanceUpsertResult(planned_count=0)

        category_ids = await self._load_category_ids(
            {instance.category for instance in instances}
            | {component.category for instance in instances for component in instance.components}
        )
        now = self._now_factory()
        rows = [
            self._instance_row(instance, category_ids=category_ids, now=now)
            for instance in instances
        ]
        insert_stmt = pg_insert(NotificationInstance.__table__).values(rows)
        upsert_stmt = (
            insert_stmt.on_conflict_do_update(
                index_elements=[
                    "tenant_id",
                    "recipient_type",
                    "recipient_id",
                    "event_type",
                    "event_key",
                    "dedupe_key",
                ],
                set_={
                    "rule_id": insert_stmt.excluded.rule_id,
                    "category_id": insert_stmt.excluded.category_id,
                    "event_id": insert_stmt.excluded.event_id,
                    "scheduled_for": insert_stmt.excluded.scheduled_for,
                    "effective_scheduled_for": insert_stmt.excluded.effective_scheduled_for,
                    "status": insert_stmt.excluded.status,
                    "status_reason": insert_stmt.excluded.status_reason,
                    "delivery_enabled": insert_stmt.excluded.delivery_enabled,
                    "priority": insert_stmt.excluded.priority,
                    "channel": insert_stmt.excluded.channel,
                    "combination_key": insert_stmt.excluded.combination_key,
                    "explanation": insert_stmt.excluded.explanation,
                    "updated_at": insert_stmt.excluded.updated_at,
                },
            )
            .returning(
                NotificationInstance.id,
                NotificationInstance.recipient_type,
                NotificationInstance.recipient_id,
                NotificationInstance.event_type,
                NotificationInstance.event_key,
                NotificationInstance.dedupe_key,
            )
        )
        result = await self._session.execute(upsert_stmt)
        instance_ids_by_key = {
            (
                row.recipient_type,
                row.recipient_id,
                row.event_type,
                row.event_key,
                row.dedupe_key,
            ): row.id
            for row in result
        }
        await self._replace_components(
            instances,
            instance_ids_by_key=instance_ids_by_key,
            category_ids=category_ids,
            now=now,
        )
        return InstanceUpsertResult(planned_count=len(instances), upserted_count=len(instances))

    async def list_instances(
        self,
        *,
        status: str | None = None,
        learner_id: int | None = None,
        event_type: EventType | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        limit: int = 100,
    ) -> tuple[NotificationInstanceRecord, ...]:
        result = await self._session.execute(
            _notification_instances_stmt(
                self._tenant_id,
                status=status,
                learner_id=learner_id,
                event_type=event_type,
                scheduled_from=scheduled_from,
                scheduled_to=scheduled_to,
                limit=limit,
            )
        )
        return tuple(_instance_record_from_row(row) for row in result.unique())

    async def get_instance(self, instance_id: int) -> NotificationInstanceRecord | None:
        result = await self._session.execute(
            _notification_instances_stmt(
                self._tenant_id,
                instance_id=instance_id,
                limit=1,
            )
        )
        row = result.unique().first()
        return _instance_record_from_row(row) if row is not None else None

    async def list_activity(
        self,
        *,
        learner_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationActivityRecord, ...]:
        attempts_result = await self._session.execute(
            _delivery_activity_stmt(
                self._tenant_id,
                learner_id=learner_id,
                limit=limit,
            )
        )
        responses_result = await self._session.execute(
            _response_activity_stmt(
                self._tenant_id,
                learner_id=learner_id,
                limit=limit,
            )
        )
        activities = [
            *(_delivery_activity_from_row(row) for row in attempts_result),
            *(_response_activity_from_row(row) for row in responses_result),
        ]
        return tuple(
            sorted(
                activities,
                key=lambda activity: activity.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:limit]
        )

    async def cancel_instance(
        self,
        instance_id: int,
        *,
        reason: str | None = None,
    ) -> NotificationInstanceRecord | None:
        instance = await self._get_instance_model(instance_id)
        if instance is None:
            return None
        if instance.status in {InstanceStatus.SENT.value, InstanceStatus.PROCESSING.value}:
            raise ValueError(f"Cannot cancel notification instance in status {instance.status}")
        now = self._now_factory()
        instance.status = InstanceStatus.CANCELLED.value
        instance.status_reason = reason or "manual_cancelled"
        instance.delivery_enabled = False
        instance.processing_started_at = None
        instance.processing_expires_at = None
        instance.updated_at = now
        await self._session.flush()
        return await self.get_instance(instance_id)

    async def schedule_instance_now(
        self,
        instance_id: int,
        *,
        now: datetime,
    ) -> NotificationInstanceRecord | None:
        instance = await self._get_instance_model(instance_id)
        if instance is None:
            return None
        if instance.status in {
            InstanceStatus.SENT.value,
            InstanceStatus.PROCESSING.value,
            InstanceStatus.SHADOW.value,
        }:
            raise ValueError(f"Cannot send notification instance now from status {instance.status}")
        instance.status = InstanceStatus.SCHEDULED.value
        instance.status_reason = "manual_send_now"
        instance.effective_scheduled_for = now
        instance.delivery_enabled = True
        instance.processing_started_at = None
        instance.processing_expires_at = None
        instance.updated_at = now
        await self._session.flush()
        return await self.get_instance(instance_id)

    async def cancel_future_instances_for_event(
        self,
        *,
        event_type: EventType,
        event_id: int,
        reason: str,
    ) -> int:
        now = self._now_factory()
        result = await self._session.execute(
            update(NotificationInstance)
            .where(
                NotificationInstance.tenant_id == self._tenant_id,
                NotificationInstance.event_type == event_type.value,
                NotificationInstance.event_id == event_id,
                NotificationInstance.status.in_(
                    (
                        InstanceStatus.SHADOW.value,
                        InstanceStatus.SCHEDULED.value,
                        InstanceStatus.SKIPPED.value,
                        InstanceStatus.SUPPRESSED.value,
                    )
                ),
            )
            .values(
                status=InstanceStatus.CANCELLED.value,
                status_reason=reason,
                delivery_enabled=False,
                processing_started_at=None,
                processing_expires_at=None,
                updated_at=now,
            )
        )
        return int(result.rowcount or 0)

    async def cancel_future_instances_for_rules_and_learners(
        self,
        *,
        rule_ids: tuple[int, ...],
        learner_ids: tuple[int, ...],
        reason: str,
    ) -> int:
        unique_rule_ids = tuple(sorted(set(rule_ids)))
        unique_learner_ids = tuple(sorted(set(learner_ids)))
        if not unique_rule_ids or not unique_learner_ids:
            return 0

        component_instance_ids = select(NotificationInstanceComponent.instance_id).where(
            NotificationInstanceComponent.rule_id.in_(unique_rule_ids)
        )
        now = self._now_factory()
        result = await self._session.execute(
            update(NotificationInstance)
            .where(
                NotificationInstance.tenant_id == self._tenant_id,
                NotificationInstance.learner_id.in_(unique_learner_ids),
                NotificationInstance.status.in_(
                    (
                        InstanceStatus.SHADOW.value,
                        InstanceStatus.SCHEDULED.value,
                        InstanceStatus.SKIPPED.value,
                        InstanceStatus.SUPPRESSED.value,
                    )
                ),
                or_(
                    NotificationInstance.rule_id.in_(unique_rule_ids),
                    NotificationInstance.id.in_(component_instance_ids),
                ),
            )
            .values(
                status=InstanceStatus.CANCELLED.value,
                status_reason=reason,
                delivery_enabled=False,
                processing_started_at=None,
                processing_expires_at=None,
                updated_at=now,
            )
        )
        return int(result.rowcount or 0)

    async def claim_due_instances(
        self,
        *,
        now: datetime,
        limit: int,
        lease_seconds: int,
    ) -> ClaimDueNotificationsResult:
        result = await self._session.execute(
            _due_instances_for_claim_stmt(self._tenant_id, now=now, limit=limit)
        )
        instances = tuple(result.scalars().all())
        if not instances:
            return ClaimDueNotificationsResult(claimed=())

        attempts: list[NotificationDeliveryAttempt] = []
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for instance in instances:
            attempt_no = await self._next_attempt_no(instance.id)
            instance.status = "processing"
            instance.processing_started_at = now
            instance.processing_expires_at = lease_expires_at
            instance.updated_at = now
            attempt = NotificationDeliveryAttempt(
                tenant_id=self._tenant_id,
                notification_instance_id=instance.id,
                attempt_no=attempt_no,
                status="processing",
                channel=instance.channel,
                provider=instance.channel,
                started_at=now,
                created_at=now,
            )
            self._session.add(attempt)
            attempts.append(attempt)

        await self._session.flush()
        chat_ids_by_learner_id = await self._load_learner_chat_ids(
            tuple(
                learner_id
                for learner_id in (instance.learner_id for instance in instances)
                if learner_id is not None
            )
        )
        return ClaimDueNotificationsResult(
            claimed=tuple(
                _claimed_instance(
                    instance,
                    attempt,
                    provider_chat_id=chat_ids_by_learner_id.get(instance.learner_id),
                )
                for instance, attempt in zip(instances, attempts)
            )
        )

    async def _get_instance_model(self, instance_id: int) -> NotificationInstance | None:
        result = await self._session.execute(
            select(NotificationInstance).where(
                NotificationInstance.tenant_id == self._tenant_id,
                NotificationInstance.id == instance_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_delivery_sent(
        self,
        *,
        instance_id: int,
        attempt_id: int,
        rendered: RenderedNotification,
        send_result: DeliverySendResult,
    ) -> None:
        instance, attempt = await self._get_delivery_pair(
            instance_id=instance_id,
            attempt_id=attempt_id,
        )
        now = send_result.sent_at
        attempt.status = "sent"
        attempt.provider = send_result.provider
        attempt.provider_chat_id = send_result.provider_chat_id
        attempt.provider_message_id = send_result.provider_message_id
        attempt.rendered_text = rendered.text
        attempt.reply_markup_snapshot = rendered.reply_markup_snapshot
        attempt.sent_at = send_result.sent_at
        attempt.finished_at = now

        instance.status = InstanceStatus.SENT.value
        instance.status_reason = None
        instance.delivery_enabled = False
        instance.processing_started_at = None
        instance.processing_expires_at = None
        instance.updated_at = now
        await self._session.flush()

    async def mark_delivery_failed(
        self,
        *,
        instance_id: int,
        attempt_id: int,
        error_code: str,
        error_message: str,
        retryable: bool,
        failed_at: datetime,
    ) -> None:
        instance, attempt = await self._get_delivery_pair(
            instance_id=instance_id,
            attempt_id=attempt_id,
        )
        attempt.status = "failed_retryable" if retryable else "failed"
        attempt.error_code = error_code
        attempt.error_message = error_message
        attempt.finished_at = failed_at

        instance.status = InstanceStatus.SCHEDULED.value if retryable else InstanceStatus.FAILED.value
        instance.status_reason = error_code
        instance.delivery_enabled = retryable
        instance.processing_started_at = None
        instance.processing_expires_at = None
        instance.updated_at = failed_at
        await self._session.flush()

    async def _get_delivery_pair(
        self,
        *,
        instance_id: int,
        attempt_id: int,
    ) -> tuple[NotificationInstance, NotificationDeliveryAttempt]:
        instance = await self._session.get(NotificationInstance, instance_id)
        attempt = await self._session.get(NotificationDeliveryAttempt, attempt_id)
        if instance is None or instance.tenant_id != self._tenant_id:
            raise ValueError(f"Notification instance {instance_id} not found")
        if (
            attempt is None
            or attempt.tenant_id != self._tenant_id
            or attempt.notification_instance_id != instance_id
        ):
            raise ValueError(f"Notification delivery attempt {attempt_id} not found")
        return instance, attempt

    async def _next_attempt_no(self, instance_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(NotificationDeliveryAttempt.attempt_no), 0) + 1).where(
                NotificationDeliveryAttempt.notification_instance_id == instance_id
            )
        )
        return result.scalar_one()

    async def _load_learner_chat_ids(self, learner_ids: tuple[int, ...]) -> dict[int, str]:
        if not learner_ids:
            return {}
        result = await self._session.execute(
            select(Learner.id, BotUser.chat_id)
            .join(BotUser, BotUser.id == Learner.bot_user_id)
            .where(
                Learner.tenant_id == self._tenant_id,
                Learner.id.in_(learner_ids),
                BotUser.chat_id.is_not(None),
            )
        )
        return {row.id: str(row.chat_id) for row in result}

    async def _load_category_ids(self, categories: set[CategoryKey]) -> dict[CategoryKey, int]:
        result = await self._session.execute(
            select(NotificationCategory.key, NotificationCategory.id).where(
                NotificationCategory.key.in_([category.value for category in categories])
            )
        )
        category_ids = {CategoryKey(row.key): row.id for row in result}
        missing = categories - set(category_ids)
        if missing:
            missing_keys = ", ".join(sorted(category.value for category in missing))
            raise ValueError(f"Missing notification categories: {missing_keys}")
        return category_ids

    def _instance_row(
        self,
        instance: NotificationInstanceDraft,
        *,
        category_ids: dict[CategoryKey, int],
        now: datetime,
    ) -> dict:
        return {
            "tenant_id": self._tenant_id,
            "rule_id": _persisted_rule_id(instance.rule_id),
            "category_id": category_ids[instance.category],
            "event_type": instance.event_type.value,
            "event_id": instance.event_id,
            "event_key": instance.event_key,
            "recipient_type": instance.recipient_type,
            "recipient_id": instance.recipient_id,
            "learner_id": instance.learner_id,
            "scheduled_for": instance.scheduled_for,
            "effective_scheduled_for": instance.effective_scheduled_for,
            "status": instance.status.value,
            "status_reason": instance.status_reason,
            "delivery_enabled": instance.delivery_enabled,
            "priority": instance.priority.value,
            "channel": instance.channel,
            "dedupe_key": instance.dedupe_key,
            "combination_key": instance.combination_key,
            "manual_overrides": {},
            "explanation": instance.explanation,
            "created_at": now,
            "updated_at": now,
        }

    async def _replace_components(
        self,
        instances: tuple[NotificationInstanceDraft, ...],
        *,
        instance_ids_by_key: dict[tuple[str, int, str, str, str], int],
        category_ids: dict[CategoryKey, int],
        now: datetime,
    ) -> None:
        component_rows: list[dict] = []
        instance_ids_with_components: list[int] = []
        for instance in instances:
            if not instance.components:
                continue
            instance_id = instance_ids_by_key[
                (
                    instance.recipient_type,
                    instance.recipient_id,
                    instance.event_type.value,
                    instance.event_key,
                    instance.dedupe_key,
                )
            ]
            instance_ids_with_components.append(instance_id)
            component_rows.extend(
                {
                    "instance_id": instance_id,
                    "rule_id": _persisted_rule_id(component.rule_id),
                    "category_id": category_ids[component.category],
                    "component_key": component.component_key,
                    "component_metadata": component.metadata,
                    "created_at": now,
                }
                for component in instance.components
            )

        if not instance_ids_with_components:
            return

        await self._session.execute(
            delete(NotificationInstanceComponent).where(
                NotificationInstanceComponent.instance_id.in_(instance_ids_with_components)
            )
        )
        await self._session.execute(insert(NotificationInstanceComponent), component_rows)


class SqlAlchemyNotificationResponseRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def record_response(self, draft: NotificationResponseDraft) -> NotificationResponseRecord:
        instance = await self._session.get(NotificationInstance, draft.notification_instance_id)
        if instance is None or instance.tenant_id != self._tenant_id:
            raise ValueError(f"Notification instance {draft.notification_instance_id} not found")

        now = self._now_factory()
        response = NotificationResponse(
            tenant_id=self._tenant_id,
            notification_instance_id=instance.id,
            event_type=instance.event_type,
            event_id=instance.event_id,
            recipient_type=instance.recipient_type,
            recipient_id=instance.recipient_id,
            learner_id=instance.learner_id,
            action_key=draft.action_key,
            response_value=draft.response_value,
            response_text=draft.response_text,
            response_metadata=draft.response_metadata,
            created_at=now,
        )
        self._session.add(response)
        await self._session.flush()

        participant_updated = False
        if instance.event_type == EventType.LESSON.value and instance.event_id and instance.learner_id:
            await self._upsert_lesson_participant_state(
                instance,
                response_value=draft.response_value,
                decline_reason=draft.response_text if draft.response_value == "declined" else None,
                response_at=now,
            )
            participant_updated = True

        return NotificationResponseRecord(
            response_id=response.id,
            notification_instance_id=instance.id,
            event_type=EventType(instance.event_type),
            event_id=instance.event_id,
            learner_id=instance.learner_id,
            response_value=draft.response_value,
            lesson_participant_state_updated=participant_updated,
        )

    async def _upsert_lesson_participant_state(
        self,
        instance: NotificationInstance,
        *,
        response_value: str,
        decline_reason: str | None,
        response_at: datetime,
    ) -> None:
        insert_stmt = pg_insert(LessonParticipantState.__table__).values(
            {
                "tenant_id": self._tenant_id,
                "lesson_id": instance.event_id,
                "learner_id": instance.learner_id,
                "response_state": response_value,
                "response_source": "notification_response",
                "response_at": response_at,
                "decline_reason": decline_reason,
                "last_notification_instance_id": instance.id,
                "created_at": response_at,
                "updated_at": response_at,
            }
        )
        await self._session.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_lesson_participant_state_lesson_learner",
                set_={
                    "tenant_id": insert_stmt.excluded.tenant_id,
                    "response_state": insert_stmt.excluded.response_state,
                    "response_source": insert_stmt.excluded.response_source,
                    "response_at": insert_stmt.excluded.response_at,
                    "decline_reason": insert_stmt.excluded.decline_reason,
                    "last_notification_instance_id": insert_stmt.excluded.last_notification_instance_id,
                    "updated_at": insert_stmt.excluded.updated_at,
                },
            )
        )


class SqlAlchemyNotificationAuditLogRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def record_audit(self, draft: NotificationAuditLogDraft) -> NotificationAuditLogRecord:
        audit = NotificationAuditLog(
            tenant_id=self._tenant_id,
            actor_type=draft.actor_type,
            actor_id=draft.actor_id,
            entity_type=draft.entity_type,
            entity_id=draft.entity_id,
            action=draft.action,
            before=draft.before,
            after=draft.after,
            reason=draft.reason,
            audit_metadata=draft.metadata,
            created_at=self._now_factory(),
        )
        self._session.add(audit)
        await self._session.flush()
        return _audit_log_record_from_model(audit)

    async def list_audit(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationAuditLogRecord, ...]:
        result = await self._session.execute(
            _notification_audit_log_stmt(
                self._tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                limit=limit,
            )
        )
        return tuple(_audit_log_record_from_model(audit) for audit in result.scalars())


class SqlAlchemyLearnerGroupRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def list_groups(self) -> tuple[LearnerGroupRecord, ...]:
        result = await self._session.execute(_learner_groups_with_counts_stmt(self._tenant_id))
        return tuple(_group_record_from_count_row(row) for row in result)

    async def get_group(self, group_id: int) -> LearnerGroupRecord | None:
        group = await self._get_group(group_id)
        if group is None:
            return None
        return await self._record_with_members(group)

    async def create_group(self, draft: LearnerGroupDraft) -> LearnerGroupRecord:
        await self._validate_learner_ids(draft.learner_ids)
        now = self._now_factory()
        group = LearnerGroup(
            tenant_id=self._tenant_id,
            name=draft.name,
            description=draft.description,
            color=draft.color,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self._session.add(group)
        await self._session.flush()
        await self._add_active_members(group.id, draft.learner_ids, now=now)
        return await self._record_with_members(group)

    async def update_group(
        self,
        group_id: int,
        draft: LearnerGroupUpdateDraft,
    ) -> LearnerGroupRecord | None:
        group = await self._get_group(group_id)
        if group is None:
            return None
        if draft.name is not None:
            group.name = draft.name
        if draft.description is not None:
            group.description = draft.description
        if draft.color is not None:
            group.color = draft.color
        if draft.status is not None:
            group.status = draft.status
        group.updated_at = self._now_factory()
        await self._session.flush()
        return await self._record_with_members(group)

    async def add_members(
        self,
        group_id: int,
        learner_ids: tuple[int, ...],
    ) -> LearnerGroupRecord | None:
        group = await self._get_group(group_id)
        if group is None:
            return None
        await self._validate_learner_ids(learner_ids)
        await self._add_active_members(group.id, learner_ids, now=self._now_factory())
        await self._session.flush()
        return await self._record_with_members(group)

    async def deactivate_member(
        self,
        group_id: int,
        learner_id: int,
    ) -> LearnerGroupRecord | None:
        group = await self._get_group(group_id)
        if group is None:
            return None
        result = await self._session.execute(
            select(GroupMember).where(
                GroupMember.tenant_id == self._tenant_id,
                GroupMember.group_id == group_id,
                GroupMember.learner_id == learner_id,
                GroupMember.status == "active",
            )
        )
        member = result.scalar_one_or_none()
        if member is not None:
            now = self._now_factory()
            member.status = "inactive"
            member.left_at = now
            member.updated_at = now
            await self._session.flush()
        return await self._record_with_members(group)

    async def _get_group(self, group_id: int) -> LearnerGroup | None:
        result = await self._session.execute(
            select(LearnerGroup).where(
                LearnerGroup.tenant_id == self._tenant_id,
                LearnerGroup.id == group_id,
            )
        )
        return result.scalar_one_or_none()

    async def _validate_learner_ids(self, learner_ids: tuple[int, ...]) -> None:
        unique_ids = tuple(sorted(set(learner_ids)))
        if not unique_ids:
            return
        result = await self._session.execute(
            select(Learner.id).where(
                Learner.tenant_id == self._tenant_id,
                Learner.id.in_(unique_ids),
            )
        )
        found_ids = set(result.scalars())
        missing_ids = set(unique_ids) - found_ids
        if missing_ids:
            raise ValueError(f"Learners not found: {', '.join(map(str, sorted(missing_ids)))}")

    async def _add_active_members(
        self,
        group_id: int,
        learner_ids: tuple[int, ...],
        *,
        now: datetime,
    ) -> None:
        unique_ids = tuple(sorted(set(learner_ids)))
        if not unique_ids:
            return
        result = await self._session.execute(
            select(GroupMember.learner_id).where(
                GroupMember.tenant_id == self._tenant_id,
                GroupMember.group_id == group_id,
                GroupMember.learner_id.in_(unique_ids),
                GroupMember.status == "active",
            )
        )
        existing_active_ids = set(result.scalars())
        for learner_id in unique_ids:
            if learner_id in existing_active_ids:
                continue
            self._session.add(
                GroupMember(
                    tenant_id=self._tenant_id,
                    group_id=group_id,
                    learner_id=learner_id,
                    status="active",
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )

    async def _record_with_members(self, group: LearnerGroup) -> LearnerGroupRecord:
        result = await self._session.execute(_group_members_stmt(self._tenant_id, group.id))
        members = tuple(_group_member_record_from_row(row) for row in result)
        return _group_record_from_model(group, members=members)


class SqlAlchemyNotificationTemplateRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def list_templates(
        self,
        *,
        include_archived: bool = False,
    ) -> tuple[NotificationTemplateRecord, ...]:
        result = await self._session.execute(
            _notification_templates_stmt(self._tenant_id, include_archived=include_archived)
        )
        return tuple(_template_record_from_model(template) for template in result.scalars().unique())

    async def get_template(self, template_id: int) -> NotificationTemplateRecord | None:
        template = await self._get_template(template_id)
        return _template_record_from_model(template) if template is not None else None

    async def create_template(self, draft: NotificationTemplateDraft) -> NotificationTemplateRecord:
        now = self._now_factory()
        template = NotificationTemplate(
            tenant_id=self._tenant_id,
            category_id=await self._category_id(draft.category),
            key=draft.key,
            name=draft.name,
            description=draft.description,
            locale=draft.locale,
            template_format=draft.template_format,
            body=draft.body,
            version=1,
            system=False,
            created_by_user_id=draft.created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(template)
        await self._session.flush()
        await self._session.refresh(template, attribute_names=["category"])
        return _template_record_from_model(template)

    async def create_template_version(
        self,
        template_id: int,
        draft: NotificationTemplateUpdateDraft,
    ) -> NotificationTemplateRecord | None:
        source = await self._get_template(template_id)
        if source is None:
            return None
        if source.system or source.tenant_id is None:
            raise ValueError("System notification templates are immutable")

        key = draft.key or source.key
        locale = draft.locale or source.locale
        now = self._now_factory()
        template = NotificationTemplate(
            tenant_id=self._tenant_id,
            category_id=await self._category_id(draft.category or CategoryKey(source.category.key)),
            key=key,
            name=draft.name or source.name,
            description=draft.description if draft.description is not None else source.description,
            locale=locale,
            template_format=draft.template_format or source.template_format,
            body=draft.body if draft.body is not None else source.body,
            version=await self._next_template_version(key=key, locale=locale),
            based_on_template_id=source.id,
            system=False,
            created_by_user_id=draft.created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(template)
        await self._session.flush()
        await self._session.refresh(template, attribute_names=["category"])
        return _template_record_from_model(template)

    async def archive_template(self, template_id: int) -> NotificationTemplateRecord | None:
        template = await self._get_template(template_id)
        if template is None:
            return None
        if template.system or template.tenant_id is None:
            raise ValueError("System notification templates are immutable")
        now = self._now_factory()
        template.archived_at = template.archived_at or now
        template.updated_at = now
        await self._session.flush()
        return _template_record_from_model(template)

    async def _get_template(self, template_id: int) -> NotificationTemplate | None:
        result = await self._session.execute(
            select(NotificationTemplate)
            .options(joinedload(NotificationTemplate.category))
            .where(
                NotificationTemplate.id == template_id,
                (NotificationTemplate.tenant_id == self._tenant_id)
                | (NotificationTemplate.tenant_id.is_(None)),
            )
        )
        return result.scalar_one_or_none()

    async def _category_id(self, category: CategoryKey) -> int:
        result = await self._session.execute(
            select(NotificationCategory.id).where(NotificationCategory.key == category.value)
        )
        category_id = result.scalar_one_or_none()
        if category_id is None:
            raise ValueError(f"Missing notification category: {category.value}")
        return category_id

    async def _next_template_version(self, *, key: str, locale: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(NotificationTemplate.version), 0) + 1).where(
                NotificationTemplate.tenant_id == self._tenant_id,
                NotificationTemplate.key == key,
                NotificationTemplate.locale == locale,
            )
        )
        return result.scalar_one()


class SqlAlchemyNotificationSettingsRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._now_factory = now_factory or _utc_now

    async def get_settings(self) -> NotificationSettingsRecord:
        system_setting = await self._get_system_setting()
        global_preference = await self._get_global_preference()
        return _settings_record_from_models(
            tenant_id=self._tenant_id,
            system_setting=system_setting,
            global_preference=global_preference,
        )

    async def update_settings(
        self,
        draft: NotificationSettingsUpdateDraft,
    ) -> NotificationSettingsRecord:
        now = self._now_factory()
        if draft.mode is not None:
            system_setting = await self._get_system_setting()
            if system_setting is None:
                system_setting = NotificationSystemSetting(
                    tenant_id=self._tenant_id,
                    mode=draft.mode.value,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(system_setting)
            else:
                system_setting.mode = draft.mode.value
                system_setting.updated_at = now

        if _has_preference_update(draft):
            preference = await self._get_global_preference()
            if preference is None:
                preference = NotificationPreference(
                    tenant_id=self._tenant_id,
                    scope_type=PreferenceScope.GLOBAL.value,
                    scope_id=None,
                    category_preferences={},
                    set_by="teacher",
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(preference)
            _apply_preference_update(preference, draft)
            preference.updated_at = now

        await self._session.flush()
        return await self.get_settings()

    async def list_learner_modes(self) -> tuple[LearnerNotificationModeRecord, ...]:
        tenant_mode = await self._tenant_mode()
        result = await self._session.execute(
            select(Learner, LearnerNotificationMode)
            .outerjoin(
                LearnerNotificationMode,
                (LearnerNotificationMode.learner_id == Learner.id)
                & (LearnerNotificationMode.tenant_id == self._tenant_id),
            )
            .where(
                Learner.tenant_id == self._tenant_id,
            )
            .order_by(Learner.display_name, Learner.id)
        )
        return tuple(
            _learner_mode_record(
                learner_id=learner.id,
                display_name=learner.display_name,
                mode_override=NotificationSystemMode(mode.mode_override) if mode is not None else NotificationSystemMode.INHERIT,
                tenant_mode=tenant_mode,
                updated_at=mode.updated_at if mode is not None else None,
            )
            for learner, mode in result
        )

    async def get_learner_mode(self, learner_id: int) -> LearnerNotificationModeRecord | None:
        learner = await self._get_learner(learner_id)
        if learner is None:
            return None
        mode = await self._get_learner_mode_model(learner_id)
        tenant_mode = await self._tenant_mode()
        return _learner_mode_record(
            learner_id=learner.id,
            display_name=learner.display_name,
            mode_override=NotificationSystemMode(mode.mode_override) if mode is not None else NotificationSystemMode.INHERIT,
            tenant_mode=tenant_mode,
            updated_at=mode.updated_at if mode is not None else None,
        )

    async def set_learner_mode(
        self,
        learner_id: int,
        draft: LearnerNotificationModeUpdateDraft,
    ) -> LearnerNotificationModeRecord | None:
        learner = await self._get_learner(learner_id)
        if learner is None:
            return None
        mode = await self._get_learner_mode_model(learner_id)
        now = self._now_factory()
        if mode is None:
            mode = LearnerNotificationMode(
                tenant_id=self._tenant_id,
                learner_id=learner_id,
                mode_override=draft.mode_override.value,
                created_at=now,
                updated_at=now,
            )
            self._session.add(mode)
        else:
            mode.mode_override = draft.mode_override.value
            mode.updated_at = now
        await self._session.flush()
        tenant_mode = await self._tenant_mode()
        return _learner_mode_record(
            learner_id=learner.id,
            display_name=learner.display_name,
            mode_override=NotificationSystemMode(mode.mode_override),
            tenant_mode=tenant_mode,
            updated_at=mode.updated_at,
        )

    async def _get_system_setting(self) -> NotificationSystemSetting | None:
        result = await self._session.execute(
            select(NotificationSystemSetting).where(NotificationSystemSetting.tenant_id == self._tenant_id)
        )
        return result.scalar_one_or_none()

    async def _get_global_preference(self) -> NotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.tenant_id == self._tenant_id,
                NotificationPreference.scope_type == PreferenceScope.GLOBAL.value,
                NotificationPreference.scope_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _tenant_mode(self) -> NotificationSystemMode:
        system_setting = await self._get_system_setting()
        if system_setting is None:
            return NotificationSystemMode.LEGACY
        return NotificationSystemMode(system_setting.mode)

    async def _get_learner(self, learner_id: int) -> Learner | None:
        result = await self._session.execute(
            select(Learner).where(
                Learner.tenant_id == self._tenant_id,
                Learner.id == learner_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_learner_mode_model(self, learner_id: int) -> LearnerNotificationMode | None:
        result = await self._session.execute(
            select(LearnerNotificationMode).where(
                LearnerNotificationMode.tenant_id == self._tenant_id,
                LearnerNotificationMode.learner_id == learner_id,
            )
        )
        return result.scalar_one_or_none()


def _persisted_rule_id(rule_id: int | str | None) -> int | None:
    if rule_id is None:
        return None
    if isinstance(rule_id, int):
        return rule_id
    raise ValueError("Notification materialization requires persisted integer rule ids")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def map_notification_rule_to_draft(rule: NotificationRule) -> NotificationRuleDraft:
    template = rule.template
    template_body = rule.inline_template_body or (template.body if template is not None else None)
    template_key = template.key if template is not None else None
    return NotificationRuleDraft(
        rule_id=rule.id,
        name=rule.name,
        category=CategoryKey(rule.category.key),
        event_type=EventType(rule.event_type),
        trigger_type=TriggerType(rule.trigger_type),
        trigger_config=rule.trigger_config or {},
        priority=Priority(rule.priority),
        template_body=template_body,
        template_key=template_key,
        combine_policy_key=rule.combine_policy_key,
        assignments=tuple(
            AudienceSelector(
                scope_type=assignment.scope_type,
                scope_id=assignment.scope_id,
                is_exclusion=assignment.is_exclusion,
            )
            for assignment in rule.assignments
        ),
    )


def map_notification_rule_to_record(rule: NotificationRule) -> NotificationRuleRecord:
    return NotificationRuleRecord(
        rule_id=rule.id,
        tenant_id=rule.tenant_id,
        preset_key=rule.preset_key,
        category=CategoryKey(rule.category.key),
        template_id=rule.template_id,
        template_key=rule.template.key if rule.template is not None else None,
        inline_template_body=rule.inline_template_body,
        inline_template_format=rule.inline_template_format,
        name=rule.name,
        description=rule.description,
        event_type=EventType(rule.event_type),
        trigger_type=TriggerType(rule.trigger_type),
        trigger_config=rule.trigger_config or {},
        priority=Priority(rule.priority),
        status=RuleStatus(rule.status),
        combine_policy_key=rule.combine_policy_key,
        delivery_channel=rule.delivery_channel,
        cap_mode=CapMode(rule.cap_mode),
        quiet_hours_mode=QuietHoursMode(rule.quiet_hours_mode),
        bypass_quiet_hours=rule.bypass_quiet_hours,
        assignments=tuple(
            AudienceSelector(
                scope_type=assignment.scope_type,
                scope_id=assignment.scope_id,
                is_exclusion=assignment.is_exclusion,
            )
            for assignment in sorted(
                rule.assignments,
                key=lambda item: (item.is_exclusion, item.scope_type, item.scope_id or 0),
            )
        ),
        created_by_user_id=rule.created_by_user_id,
        activated_at=rule.activated_at,
        paused_at=rule.paused_at,
        archived_at=rule.archived_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _active_rules_stmt(tenant_id: int):
    return (
        select(NotificationRule)
        .options(
            joinedload(NotificationRule.category),
            joinedload(NotificationRule.template),
            selectinload(NotificationRule.assignments),
        )
        .where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.status == "active",
            NotificationRule.archived_at.is_(None),
        )
        .order_by(NotificationRule.id)
    )


def _active_rules_for_group_stmt(tenant_id: int, group_id: int):
    return (
        select(NotificationRule)
        .options(
            joinedload(NotificationRule.category),
            joinedload(NotificationRule.template),
            selectinload(NotificationRule.assignments),
        )
        .join(NotificationAssignment, NotificationAssignment.rule_id == NotificationRule.id)
        .where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.status == "active",
            NotificationRule.archived_at.is_(None),
            NotificationAssignment.tenant_id == tenant_id,
            NotificationAssignment.scope_type == "group",
            NotificationAssignment.scope_id == group_id,
            NotificationAssignment.is_exclusion.is_(False),
        )
        .order_by(NotificationRule.id)
    )


def _notification_rules_stmt(tenant_id: int, *, include_archived: bool):
    stmt = (
        select(NotificationRule)
        .options(
            joinedload(NotificationRule.category),
            joinedload(NotificationRule.template),
            selectinload(NotificationRule.assignments),
        )
        .where(NotificationRule.tenant_id == tenant_id)
        .order_by(NotificationRule.created_at.desc(), NotificationRule.id.desc())
    )
    if not include_archived:
        stmt = stmt.where(
            NotificationRule.status != RuleStatus.ARCHIVED.value,
            NotificationRule.archived_at.is_(None),
        )
    return stmt


def _queued_jobs_for_claim_stmt(tenant_id: int, *, job_type: str, limit: int):
    return (
        select(NotificationJob)
        .where(
            NotificationJob.tenant_id == tenant_id,
            NotificationJob.job_type == job_type,
            NotificationJob.status == "queued",
        )
        .order_by(NotificationJob.created_at, NotificationJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


def _due_instances_for_claim_stmt(tenant_id: int, *, now: datetime, limit: int):
    return (
        select(NotificationInstance)
        .options(joinedload(NotificationInstance.category))
        .where(
            NotificationInstance.tenant_id == tenant_id,
            NotificationInstance.status == "scheduled",
            NotificationInstance.delivery_enabled.is_(True),
            NotificationInstance.effective_scheduled_for <= now,
        )
        .order_by(NotificationInstance.effective_scheduled_for, NotificationInstance.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )


def _notification_instances_stmt(
    tenant_id: int,
    *,
    instance_id: int | None = None,
    status: str | None = None,
    learner_id: int | None = None,
    event_type: EventType | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: int = 100,
):
    stmt = (
        select(NotificationInstance, Learner.display_name.label("learner_display_name"))
        .options(
            joinedload(NotificationInstance.category),
            joinedload(NotificationInstance.rule),
            selectinload(NotificationInstance.components).joinedload(NotificationInstanceComponent.category),
            selectinload(NotificationInstance.attempts),
        )
        .outerjoin(
            Learner,
            (Learner.id == NotificationInstance.learner_id)
            & (Learner.tenant_id == NotificationInstance.tenant_id),
        )
        .where(NotificationInstance.tenant_id == tenant_id)
        .order_by(NotificationInstance.effective_scheduled_for, NotificationInstance.id)
        .limit(limit)
    )
    if instance_id is not None:
        stmt = stmt.where(NotificationInstance.id == instance_id)
    if status is not None:
        stmt = stmt.where(NotificationInstance.status == status)
    if learner_id is not None:
        stmt = stmt.where(NotificationInstance.learner_id == learner_id)
    if event_type is not None:
        stmt = stmt.where(NotificationInstance.event_type == event_type.value)
    if scheduled_from is not None:
        stmt = stmt.where(NotificationInstance.effective_scheduled_for >= scheduled_from)
    if scheduled_to is not None:
        stmt = stmt.where(NotificationInstance.effective_scheduled_for < scheduled_to)
    return stmt


def _delivery_activity_stmt(
    tenant_id: int,
    *,
    learner_id: int | None = None,
    limit: int = 100,
):
    occurred_at = func.coalesce(
        NotificationDeliveryAttempt.finished_at,
        NotificationDeliveryAttempt.sent_at,
        NotificationDeliveryAttempt.started_at,
        NotificationDeliveryAttempt.created_at,
    )
    stmt = (
        select(
            NotificationDeliveryAttempt,
            NotificationInstance.id.label("instance_id"),
            NotificationInstance.event_type,
            NotificationInstance.event_id,
            NotificationInstance.learner_id,
            NotificationCategory.key.label("category_key"),
            Learner.display_name.label("learner_display_name"),
            occurred_at.label("occurred_at"),
        )
        .join(NotificationInstance, NotificationInstance.id == NotificationDeliveryAttempt.notification_instance_id)
        .join(NotificationCategory, NotificationCategory.id == NotificationInstance.category_id)
        .outerjoin(
            Learner,
            (Learner.id == NotificationInstance.learner_id)
            & (Learner.tenant_id == NotificationInstance.tenant_id),
        )
        .where(NotificationDeliveryAttempt.tenant_id == tenant_id)
        .order_by(occurred_at.desc(), NotificationDeliveryAttempt.id.desc())
        .limit(limit)
    )
    if learner_id is not None:
        stmt = stmt.where(NotificationInstance.learner_id == learner_id)
    return stmt


def _response_activity_stmt(
    tenant_id: int,
    *,
    learner_id: int | None = None,
    limit: int = 100,
):
    stmt = (
        select(
            NotificationResponse,
            NotificationResponse.notification_instance_id.label("instance_id"),
            NotificationResponse.event_type,
            NotificationResponse.event_id,
            NotificationResponse.learner_id,
            NotificationCategory.key.label("category_key"),
            Learner.display_name.label("learner_display_name"),
            NotificationResponse.created_at.label("occurred_at"),
        )
        .outerjoin(NotificationInstance, NotificationInstance.id == NotificationResponse.notification_instance_id)
        .outerjoin(NotificationCategory, NotificationCategory.id == NotificationInstance.category_id)
        .outerjoin(
            Learner,
            (Learner.id == NotificationResponse.learner_id)
            & (Learner.tenant_id == NotificationResponse.tenant_id),
        )
        .where(NotificationResponse.tenant_id == tenant_id)
        .order_by(NotificationResponse.created_at.desc(), NotificationResponse.id.desc())
        .limit(limit)
    )
    if learner_id is not None:
        stmt = stmt.where(NotificationResponse.learner_id == learner_id)
    return stmt


def _notification_audit_log_stmt(
    tenant_id: int,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 100,
):
    stmt = (
        select(NotificationAuditLog)
        .where(NotificationAuditLog.tenant_id == tenant_id)
        .order_by(NotificationAuditLog.created_at.desc(), NotificationAuditLog.id.desc())
        .limit(limit)
    )
    if entity_type is not None:
        stmt = stmt.where(NotificationAuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(NotificationAuditLog.entity_id == entity_id)
    return stmt


def _learner_groups_with_counts_stmt(tenant_id: int):
    active_member_count = func.count(GroupMember.id).filter(GroupMember.status == "active")
    return (
        select(
            LearnerGroup.id,
            LearnerGroup.name,
            LearnerGroup.description,
            LearnerGroup.color,
            LearnerGroup.status,
            LearnerGroup.created_at,
            LearnerGroup.updated_at,
            active_member_count.label("member_count"),
        )
        .outerjoin(
            GroupMember,
            (GroupMember.group_id == LearnerGroup.id)
            & (GroupMember.tenant_id == LearnerGroup.tenant_id),
        )
        .where(LearnerGroup.tenant_id == tenant_id)
        .group_by(LearnerGroup.id)
        .order_by(LearnerGroup.name, LearnerGroup.id)
    )


def _notification_templates_stmt(tenant_id: int, *, include_archived: bool):
    stmt = (
        select(NotificationTemplate)
        .options(joinedload(NotificationTemplate.category))
        .where(
            (NotificationTemplate.tenant_id == tenant_id)
            | (NotificationTemplate.tenant_id.is_(None))
        )
        .order_by(NotificationTemplate.system.desc(), NotificationTemplate.key, NotificationTemplate.version.desc())
    )
    if not include_archived:
        stmt = stmt.where(NotificationTemplate.archived_at.is_(None))
    return stmt


def _group_members_stmt(tenant_id: int, group_id: int):
    return (
        select(
            GroupMember.learner_id,
            GroupMember.status,
            GroupMember.joined_at,
            GroupMember.left_at,
            Learner.display_name,
        )
        .join(Learner, Learner.id == GroupMember.learner_id)
        .where(
            GroupMember.tenant_id == tenant_id,
            GroupMember.group_id == group_id,
        )
        .order_by(GroupMember.status, Learner.display_name, GroupMember.learner_id)
    )


def _learner_recipients_stmt(tenant_id: int, learner_ids: tuple[int, ...]):
    return (
        select(
            Learner.id.label("learner_id"),
            Learner.display_name,
            Learner.notifications_enabled,
            BotUser.chat_id,
        )
        .join(BotUser, BotUser.id == Learner.bot_user_id)
        .where(
            Learner.tenant_id == tenant_id,
            Learner.id.in_(learner_ids),
        )
        .order_by(Learner.display_name, Learner.id)
    )


def _lesson_events_stmt(
    tenant_id: int,
    learner_ids: tuple[int, ...],
    *,
    starts_at: datetime,
    ends_at: datetime,
    limit: int,
):
    conflict_count, conflict_lesson_ids, conflict_package_ids = _lesson_slot_conflict_columns(tenant_id)
    return (
        select(
            Lesson.id.label("event_id"),
            Lesson.scheduled_at.label("starts_at"),
            Lesson.duration_minutes,
            Lesson.status.label("lesson_status"),
            Lesson.has_homework,
            Lesson.homework_due_at,
            Lesson.sequence_index,
            LessonPackage.id.label("package_id"),
            LessonPackage.title.label("package_title"),
            LessonPackage.status.label("package_status"),
            LessonPackage.timezone,
            LessonPackage.learner_id,
            conflict_count,
            conflict_lesson_ids,
            conflict_package_ids,
        )
        .join(LessonPackage, LessonPackage.id == Lesson.package_id)
        .where(
            Lesson.tenant_id == tenant_id,
            LessonPackage.learner_id.in_(learner_ids),
            Lesson.scheduled_at >= starts_at,
            Lesson.scheduled_at < ends_at,
        )
        .order_by(Lesson.scheduled_at, Lesson.id)
        .limit(limit)
    )


def _lesson_event_by_id_stmt(tenant_id: int, event_id: int):
    conflict_count, conflict_lesson_ids, conflict_package_ids = _lesson_slot_conflict_columns(tenant_id)
    return (
        select(
            Lesson.id.label("event_id"),
            Lesson.scheduled_at.label("starts_at"),
            Lesson.duration_minutes,
            Lesson.status.label("lesson_status"),
            Lesson.has_homework,
            Lesson.homework_due_at,
            Lesson.sequence_index,
            LessonPackage.id.label("package_id"),
            LessonPackage.title.label("package_title"),
            LessonPackage.status.label("package_status"),
            LessonPackage.timezone,
            LessonPackage.learner_id,
            conflict_count,
            conflict_lesson_ids,
            conflict_package_ids,
        )
        .join(LessonPackage, LessonPackage.id == Lesson.package_id)
        .where(
            Lesson.tenant_id == tenant_id,
            Lesson.id == event_id,
        )
    )


def _lesson_slot_conflict_columns(tenant_id: int):
    conflict_lesson = aliased(Lesson)
    conflict_package = aliased(LessonPackage)
    base_filters = (
        conflict_lesson.tenant_id == tenant_id,
        conflict_package.tenant_id == tenant_id,
        conflict_package.learner_id == LessonPackage.learner_id,
        conflict_lesson.scheduled_at == Lesson.scheduled_at,
        conflict_lesson.status.in_(("scheduled", "rescheduled")),
        conflict_package.status == "active",
    )
    conflict_count = (
        select(func.count(conflict_lesson.id))
        .select_from(conflict_lesson)
        .join(conflict_package, conflict_package.id == conflict_lesson.package_id)
        .where(*base_filters)
        .correlate(Lesson, LessonPackage)
        .scalar_subquery()
        .label("calendar_conflict_count")
    )
    conflict_lesson_ids = (
        select(func.array_agg(conflict_lesson.id))
        .select_from(conflict_lesson)
        .join(conflict_package, conflict_package.id == conflict_lesson.package_id)
        .where(*base_filters)
        .correlate(Lesson, LessonPackage)
        .scalar_subquery()
        .label("calendar_conflict_lesson_ids")
    )
    conflict_package_ids = (
        select(func.array_agg(conflict_lesson.package_id))
        .select_from(conflict_lesson)
        .join(conflict_package, conflict_package.id == conflict_lesson.package_id)
        .where(*base_filters)
        .correlate(Lesson, LessonPackage)
        .scalar_subquery()
        .label("calendar_conflict_package_ids")
    )
    return conflict_count, conflict_lesson_ids, conflict_package_ids


def _package_events_stmt(
    tenant_id: int,
    learner_ids: tuple[int, ...],
    *,
    starts_at: datetime,
    ends_at: datetime,
    limit: int,
):
    return (
        select(
            LessonPackage.id.label("event_id"),
            LessonPackage.end_date.label("starts_at"),
            LessonPackage.status.label("package_status"),
            LessonPackage.title.label("package_title"),
            LessonPackage.timezone,
            LessonPackage.learner_id,
        )
        .where(
            LessonPackage.tenant_id == tenant_id,
            LessonPackage.learner_id.in_(learner_ids),
            LessonPackage.end_date.is_not(None),
            LessonPackage.end_date >= starts_at,
            LessonPackage.end_date < ends_at,
        )
        .order_by(LessonPackage.end_date, LessonPackage.id)
        .limit(limit)
    )


def _package_event_by_id_stmt(tenant_id: int, event_id: int):
    return (
        select(
            LessonPackage.id.label("event_id"),
            LessonPackage.end_date.label("starts_at"),
            LessonPackage.status.label("package_status"),
            LessonPackage.title.label("package_title"),
            LessonPackage.timezone,
            LessonPackage.learner_id,
        )
        .where(
            LessonPackage.tenant_id == tenant_id,
            LessonPackage.id == event_id,
            LessonPackage.end_date.is_not(None),
        )
    )


def _recipient_from_row(row) -> PreviewRecipient:
    return PreviewRecipient(
        learner_id=row.learner_id,
        display_name=row.display_name,
        notifications_enabled=row.notifications_enabled,
        has_contact=row.chat_id is not None,
        timezone="Europe/Moscow",
    )


def _lesson_event_from_row(row) -> PreviewEvent:
    ends_at = None
    if row.starts_at is not None and row.duration_minutes is not None:
        ends_at = row.starts_at + timedelta(minutes=row.duration_minutes)
    return PreviewEvent(
        event_type=EventType.LESSON,
        event_id=row.event_id,
        learner_id=row.learner_id,
        starts_at=row.starts_at,
        ends_at=ends_at,
        timezone=row.timezone or "Europe/Moscow",
        package_status=row.package_status,
        lesson_status=row.lesson_status,
        has_homework=row.has_homework,
        metadata={
            "package_id": row.package_id,
            "package_title": row.package_title,
            "sequence_index": row.sequence_index,
            "homework_due_at": row.homework_due_at,
            "calendar_conflict_count": getattr(row, "calendar_conflict_count", 0) or 0,
            "calendar_conflict_lesson_ids": tuple(getattr(row, "calendar_conflict_lesson_ids", None) or ()),
            "calendar_conflict_package_ids": tuple(getattr(row, "calendar_conflict_package_ids", None) or ()),
        },
    )


def _package_event_from_row(row) -> PreviewEvent:
    return PreviewEvent(
        event_type=EventType.PACKAGE,
        event_id=row.event_id,
        learner_id=row.learner_id,
        starts_at=row.starts_at,
        timezone=row.timezone or "Europe/Moscow",
        package_status=row.package_status,
        metadata={
            "package_title": row.package_title,
        },
    )


def _preference_from_model(model: NotificationPreference | None) -> DomainNotificationPreference | None:
    if model is None:
        return None
    return DomainNotificationPreference(
        scope_type=PreferenceScope(model.scope_type),
        scope_id=model.scope_id,
        notifications_enabled=model.notifications_enabled,
        quiet_hours=_quiet_hours_from_model(model),
        timezone=model.timezone,
        daily_cap=model.daily_cap,
        cap_mode=CapMode(model.cap_mode) if model.cap_mode else None,
        category_enabled={
            CategoryKey(key): enabled
            for key, enabled in (model.category_preferences or {}).items()
        },
    )


def _quiet_hours_from_model(model: NotificationPreference) -> QuietHours | None:
    if not model.quiet_hours_start or not model.quiet_hours_end:
        return None
    return QuietHours(
        start=time.fromisoformat(model.quiet_hours_start),
        end=time.fromisoformat(model.quiet_hours_end),
        mode=QuietHoursMode.SHIFT,
    )


def _job_record_from_model(job: NotificationJob) -> NotificationJobRecord:
    return NotificationJobRecord(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        scope=job.scope or {},
    )


def _audit_log_record_from_model(audit: NotificationAuditLog) -> NotificationAuditLogRecord:
    return NotificationAuditLogRecord(
        audit_id=audit.id,
        actor_type=audit.actor_type,
        actor_id=audit.actor_id,
        entity_type=audit.entity_type,
        entity_id=audit.entity_id,
        action=audit.action,
        before=audit.before,
        after=audit.after,
        reason=audit.reason,
        metadata=audit.audit_metadata or {},
        created_at=audit.created_at,
    )


def _instance_record_from_row(row) -> NotificationInstanceRecord:
    instance = row[0]
    return NotificationInstanceRecord(
        instance_id=instance.id,
        rule_id=instance.rule_id,
        category=CategoryKey(instance.category.key),
        event_type=EventType(instance.event_type),
        event_id=instance.event_id,
        event_key=instance.event_key,
        recipient_type=instance.recipient_type,
        recipient_id=instance.recipient_id,
        learner_id=instance.learner_id,
        learner_display_name=row.learner_display_name,
        scheduled_for=instance.scheduled_for,
        effective_scheduled_for=instance.effective_scheduled_for,
        status=InstanceStatus(instance.status),
        status_reason=instance.status_reason,
        delivery_enabled=instance.delivery_enabled,
        priority=Priority(instance.priority),
        channel=instance.channel,
        dedupe_key=instance.dedupe_key,
        combination_key=instance.combination_key,
        explanation=instance.explanation or {},
        components=tuple(_instance_component_record(component) for component in instance.components),
        latest_attempt=_latest_attempt_record(instance.attempts),
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def _instance_component_record(component: NotificationInstanceComponent) -> NotificationInstanceComponentRecord:
    return NotificationInstanceComponentRecord(
        component_id=component.id,
        rule_id=component.rule_id,
        category=CategoryKey(component.category.key),
        template_id=component.template_id,
        component_key=component.component_key,
        metadata=component.component_metadata or {},
    )


def _latest_attempt_record(
    attempts: list[NotificationDeliveryAttempt],
) -> NotificationDeliveryAttemptRecord | None:
    if not attempts:
        return None
    return _attempt_record_from_model(
        max(
            attempts,
            key=lambda attempt: (
                attempt.finished_at
                or attempt.sent_at
                or attempt.started_at
                or attempt.created_at
                or datetime.min.replace(tzinfo=timezone.utc),
                attempt.id or 0,
            ),
        )
    )


def _attempt_record_from_model(attempt: NotificationDeliveryAttempt) -> NotificationDeliveryAttemptRecord:
    return NotificationDeliveryAttemptRecord(
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        channel=attempt.channel,
        provider=attempt.provider,
        provider_chat_id=attempt.provider_chat_id,
        provider_message_id=attempt.provider_message_id,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
        started_at=attempt.started_at,
        sent_at=attempt.sent_at,
        finished_at=attempt.finished_at,
        created_at=attempt.created_at,
    )


def _delivery_activity_from_row(row) -> NotificationActivityRecord:
    attempt = row[0]
    return NotificationActivityRecord(
        activity_type="delivery_attempt",
        activity_id=attempt.id,
        notification_instance_id=row.instance_id,
        category=CategoryKey(row.category_key),
        event_type=EventType(row.event_type),
        event_id=row.event_id,
        learner_id=row.learner_id,
        learner_display_name=row.learner_display_name,
        status=attempt.status,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
        provider_message_id=attempt.provider_message_id,
        occurred_at=row.occurred_at,
        metadata={
            "attempt_no": attempt.attempt_no,
            "channel": attempt.channel,
            "provider": attempt.provider,
        },
    )


def _response_activity_from_row(row) -> NotificationActivityRecord:
    response = row[0]
    return NotificationActivityRecord(
        activity_type="response",
        activity_id=response.id,
        notification_instance_id=row.instance_id,
        category=CategoryKey(row.category_key) if row.category_key else None,
        event_type=EventType(row.event_type),
        event_id=row.event_id,
        learner_id=row.learner_id,
        learner_display_name=row.learner_display_name,
        status=response.response_value,
        action_key=response.action_key,
        response_value=response.response_value,
        occurred_at=row.occurred_at,
        metadata=response.response_metadata or {},
    )


def _group_record_from_count_row(row) -> LearnerGroupRecord:
    return LearnerGroupRecord(
        group_id=row.id,
        name=row.name,
        description=row.description,
        color=row.color,
        status=row.status,
        member_count=int(row.member_count or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _group_record_from_model(
    group: LearnerGroup,
    *,
    members: tuple[LearnerGroupMemberRecord, ...],
) -> LearnerGroupRecord:
    return LearnerGroupRecord(
        group_id=group.id,
        name=group.name,
        description=group.description,
        color=group.color,
        status=group.status,
        member_count=sum(1 for member in members if member.status == "active"),
        members=members,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _group_member_record_from_row(row) -> LearnerGroupMemberRecord:
    return LearnerGroupMemberRecord(
        learner_id=row.learner_id,
        display_name=row.display_name,
        status=row.status,
        joined_at=row.joined_at,
        left_at=row.left_at,
    )


def _template_record_from_model(template: NotificationTemplate) -> NotificationTemplateRecord:
    return NotificationTemplateRecord(
        template_id=template.id,
        tenant_id=template.tenant_id,
        category=CategoryKey(template.category.key),
        key=template.key,
        name=template.name,
        body=template.body,
        description=template.description,
        locale=template.locale,
        template_format=template.template_format,
        version=template.version,
        system=template.system,
        based_on_template_id=template.based_on_template_id,
        archived_at=template.archived_at,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _settings_record_from_models(
    *,
    tenant_id: int,
    system_setting: NotificationSystemSetting | None,
    global_preference: NotificationPreference | None,
) -> NotificationSettingsRecord:
    return NotificationSettingsRecord(
        tenant_id=tenant_id,
        mode=(
            NotificationSystemMode(system_setting.mode)
            if system_setting is not None
            else NotificationSystemMode.LEGACY
        ),
        notifications_enabled=global_preference.notifications_enabled if global_preference is not None else None,
        quiet_hours_start=global_preference.quiet_hours_start if global_preference is not None else None,
        quiet_hours_end=global_preference.quiet_hours_end if global_preference is not None else None,
        timezone=global_preference.timezone if global_preference is not None else None,
        daily_cap=global_preference.daily_cap if global_preference is not None else None,
        cap_mode=(
            CapMode(global_preference.cap_mode)
            if global_preference is not None and global_preference.cap_mode
            else None
        ),
        category_preferences=dict(global_preference.category_preferences or {})
        if global_preference is not None
        else {},
        updated_at=_latest_datetime(
            system_setting.updated_at if system_setting is not None else None,
            global_preference.updated_at if global_preference is not None else None,
        ),
    )


def _has_preference_update(draft: NotificationSettingsUpdateDraft) -> bool:
    return any(
        (
            draft.notifications_enabled_set,
            draft.quiet_hours_start_set,
            draft.quiet_hours_end_set,
            draft.timezone_set,
            draft.daily_cap_set,
            draft.cap_mode_set,
            draft.category_preferences_set,
        )
    )


def _apply_preference_update(
    preference: NotificationPreference,
    draft: NotificationSettingsUpdateDraft,
) -> None:
    if draft.notifications_enabled_set:
        preference.notifications_enabled = draft.notifications_enabled
    if draft.quiet_hours_start_set:
        preference.quiet_hours_start = draft.quiet_hours_start
    if draft.quiet_hours_end_set:
        preference.quiet_hours_end = draft.quiet_hours_end
    if draft.timezone_set:
        preference.timezone = draft.timezone
    if draft.daily_cap_set:
        preference.daily_cap = draft.daily_cap
    if draft.cap_mode_set:
        preference.cap_mode = draft.cap_mode.value if draft.cap_mode is not None else None
    if draft.category_preferences_set:
        preference.category_preferences = draft.category_preferences or {}


def _learner_mode_record_from_row(
    row,
    *,
    tenant_mode: NotificationSystemMode,
) -> LearnerNotificationModeRecord:
    mode = row[0]
    return _learner_mode_record(
        learner_id=mode.learner_id,
        display_name=row.display_name,
        mode_override=NotificationSystemMode(mode.mode_override),
        tenant_mode=tenant_mode,
        updated_at=mode.updated_at,
    )


def _learner_mode_record(
    *,
    learner_id: int,
    display_name: str,
    mode_override: NotificationSystemMode,
    tenant_mode: NotificationSystemMode,
    updated_at: datetime | None,
) -> LearnerNotificationModeRecord:
    return LearnerNotificationModeRecord(
        learner_id=learner_id,
        display_name=display_name,
        mode_override=mode_override,
        effective_mode=tenant_mode if mode_override == NotificationSystemMode.INHERIT else mode_override,
        updated_at=updated_at,
    )


def _latest_datetime(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _claimed_instance(
    instance: NotificationInstance,
    attempt: NotificationDeliveryAttempt,
    *,
    provider_chat_id: str | None = None,
) -> ClaimedNotificationInstance:
    return ClaimedNotificationInstance(
        instance_id=instance.id,
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        rule_id=instance.rule_id,
        category=CategoryKey(instance.category.key),
        event_type=EventType(instance.event_type),
        event_id=instance.event_id,
        recipient_type=instance.recipient_type,
        recipient_id=instance.recipient_id,
        learner_id=instance.learner_id,
        effective_scheduled_for=instance.effective_scheduled_for,
        priority=Priority(instance.priority),
        channel=instance.channel,
        provider_chat_id=provider_chat_id,
        explanation=instance.explanation or {},
    )
