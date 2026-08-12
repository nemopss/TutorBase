from __future__ import annotations

from notifications.application.dto import (
    AudienceSelector,
    InstanceUpsertResult,
    MaterializeRulesResult,
    NotificationJobDraft,
    NotificationJobRecord,
    PreviewEvent,
    PreviewRecipient,
    ReconcileNotificationGroupMembershipResult,
    ReconcileNotificationEventResult,
)
from notifications.application.materialization import _is_live_materialization, _materialize_rules
from notifications.application.ports import (
    AudienceResolver,
    EventRepository,
    NotificationMaterializationUnitOfWork,
)
from notifications.domain.enums import EventType, InstanceStatus, NotificationSystemMode


class QueueNotificationEventReconciliationUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        event_type: EventType,
        event_id: int,
        reason: str = "event_changed",
        delivery_enabled: bool = False,
        shadow: bool = True,
        horizon_days: int = 30,
        limit: int = 100,
        created_by_user_id: int | None = None,
        commit: bool = True,
    ) -> NotificationJobRecord:
        job = await self._uow.jobs.create_job(
            NotificationJobDraft(
                job_type="reconcile_event",
                scope={
                    "event_type": event_type.value,
                    "event_id": event_id,
                    "reason": reason,
                    "delivery_enabled": delivery_enabled,
                    "shadow": shadow,
                    "horizon_days": horizon_days,
                    "limit": limit,
                },
                created_by_user_id=created_by_user_id,
                dedupe_key=f"reconcile_event:{event_type.value}:{event_id}",
            )
        )
        if commit:
            await self._uow.commit()
        return job


class QueueNotificationGroupMembershipReconciliationUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        group_id: int,
        learner_ids: tuple[int, ...],
        reason: str = "group_membership_changed",
        delivery_enabled: bool | None = None,
        shadow: bool | None = None,
        horizon_days: int = 30,
        limit: int = 100,
        created_by_user_id: int | None = None,
        commit: bool = True,
    ) -> NotificationJobRecord:
        scoped_learner_ids = tuple(sorted(set(learner_ids)))
        effective_delivery_enabled, effective_shadow = await self._resolve_delivery_mode(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
        job = await self._uow.jobs.create_job(
            NotificationJobDraft(
                job_type="reconcile_group_membership",
                scope={
                    "group_id": group_id,
                    "learner_ids": list(scoped_learner_ids),
                    "reason": reason,
                    "delivery_enabled": effective_delivery_enabled,
                    "shadow": effective_shadow,
                    "horizon_days": horizon_days,
                    "limit": limit,
                },
                created_by_user_id=created_by_user_id,
                dedupe_key=f"reconcile_group_membership:{group_id}",
            )
        )
        if commit:
            await self._uow.commit()
        return job

    async def _resolve_delivery_mode(
        self,
        *,
        delivery_enabled: bool | None,
        shadow: bool | None,
    ) -> tuple[bool, bool]:
        if delivery_enabled is not None and shadow is not None:
            return delivery_enabled, shadow

        settings = await self._uow.settings.get_settings()
        resolved_delivery_enabled = (
            delivery_enabled
            if delivery_enabled is not None
            else settings.mode == NotificationSystemMode.NEW
        )
        resolved_shadow = shadow if shadow is not None else not resolved_delivery_enabled
        return resolved_delivery_enabled, resolved_shadow


class RunReconcileNotificationEventJobUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, job: NotificationJobRecord) -> ReconcileNotificationEventResult:
        if job.job_type != "reconcile_event":
            raise ValueError(f"Unsupported notification job type: {job.job_type}")
        if job.status != "running":
            raise ValueError(f"Notification job {job.job_id} is not running")

        event_type = EventType(job.scope["event_type"])
        event_id = int(job.scope["event_id"])
        reason = str(job.scope.get("reason", "event_changed"))
        delivery_enabled = bool(job.scope.get("delivery_enabled", False))
        shadow = bool(job.scope.get("shadow", True))
        horizon_days = int(job.scope.get("horizon_days", 30))
        limit = int(job.scope.get("limit", 100))
        live_materialization = _is_live_materialization(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )

        cancelled_count = await self._uow.instances.cancel_future_instances_for_event(
            event_type=event_type,
            event_id=event_id,
            reason=f"reconciled:{reason}",
            statuses=_reconciliation_cancel_statuses(
                delivery_enabled=delivery_enabled,
                shadow=shadow,
            ),
        )
        event = await self._uow.events.get_event(event_type=event_type, event_id=event_id)
        if event is None:
            materialization = MaterializeRulesResult(
                planned_instances=(),
                upsert_result=InstanceUpsertResult(planned_count=0),
                warnings=("event_not_found",),
            )
            succeeded = await self._mark_succeeded(
                job,
                materialization=materialization,
                event_found=False,
                cancelled_count=cancelled_count,
            )
            await self._uow.commit()
            return ReconcileNotificationEventResult(
                job=succeeded,
                materialization=materialization,
                event_found=False,
                cancelled_count=cancelled_count,
        )

        rules = tuple(rule for rule in await self._uow.rules.list_active_rules() if rule.event_type == event_type)
        materialization = await _materialize_rules(
            _ScopedEventUnitOfWork(self._uow, event),
            rules,
            horizon_days=horizon_days,
            limit=limit,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
            commit=False,
            respect_rollout_modes=True,
            skip_past_due=live_materialization,
        )
        succeeded = await self._mark_succeeded(
            job,
            materialization=materialization,
            event_found=True,
            cancelled_count=cancelled_count,
        )
        await self._uow.commit()
        return ReconcileNotificationEventResult(
            job=succeeded,
            materialization=materialization,
            event_found=True,
            cancelled_count=cancelled_count,
        )

    async def _mark_succeeded(
        self,
        job: NotificationJobRecord,
        *,
        materialization: MaterializeRulesResult,
        event_found: bool,
        cancelled_count: int,
    ) -> NotificationJobRecord:
        return await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "event_found": event_found,
                "cancelled_count": cancelled_count,
                "planned_count": materialization.upsert_result.planned_count,
                "upserted_count": materialization.upsert_result.upserted_count,
                "warnings": list(materialization.warnings),
            },
        )


class RunReconcileNotificationGroupMembershipJobUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, job: NotificationJobRecord) -> ReconcileNotificationGroupMembershipResult:
        if job.job_type != "reconcile_group_membership":
            raise ValueError(f"Unsupported notification job type: {job.job_type}")
        if job.status != "running":
            raise ValueError(f"Notification job {job.job_id} is not running")

        group_id = int(job.scope["group_id"])
        learner_ids = tuple(sorted({int(learner_id) for learner_id in job.scope.get("learner_ids", [])}))
        reason = str(job.scope.get("reason", "group_membership_changed"))
        delivery_enabled = bool(job.scope.get("delivery_enabled", False))
        shadow = bool(job.scope.get("shadow", True))
        horizon_days = int(job.scope.get("horizon_days", 30))
        limit = int(job.scope.get("limit", 100))
        live_materialization = _is_live_materialization(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )

        rules = await self._uow.rules.list_active_rules_for_group(group_id)
        rule_ids = tuple(int(rule.rule_id) for rule in rules)
        cancelled_count = await self._uow.instances.cancel_future_instances_for_rules_and_learners(
            rule_ids=rule_ids,
            learner_ids=learner_ids,
            reason=f"reconciled:{reason}",
            statuses=_reconciliation_cancel_statuses(
                delivery_enabled=delivery_enabled,
                shadow=shadow,
            ),
        )
        if not rules or not learner_ids:
            warning = "no_group_rules" if not rules else "empty_learner_scope"
            materialization = MaterializeRulesResult(
                planned_instances=(),
                upsert_result=InstanceUpsertResult(planned_count=0),
                warnings=(warning,),
            )
        else:
            materialization = await _materialize_rules(
                _LearnerScopedAudienceUnitOfWork(self._uow, learner_ids),
                rules,
                horizon_days=horizon_days,
                limit=limit,
                delivery_enabled=delivery_enabled,
                shadow=shadow,
                commit=False,
                respect_rollout_modes=True,
                skip_past_due=live_materialization,
            )

        succeeded = await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "group_id": group_id,
                "learner_ids": list(learner_ids),
                "rules_count": len(rules),
                "cancelled_count": cancelled_count,
                "planned_count": materialization.upsert_result.planned_count,
                "upserted_count": materialization.upsert_result.upserted_count,
                "warnings": list(materialization.warnings),
            },
        )
        await self._uow.commit()
        return ReconcileNotificationGroupMembershipResult(
            job=succeeded,
            materialization=materialization,
            group_id=group_id,
            learner_ids=learner_ids,
            rules_count=len(rules),
            cancelled_count=cancelled_count,
        )


def _reconciliation_cancel_statuses(
    *,
    delivery_enabled: bool,
    shadow: bool,
) -> tuple[InstanceStatus, ...] | None:
    if shadow and not delivery_enabled:
        return (InstanceStatus.SHADOW,)
    return None


class _SingleEventRepository:
    def __init__(self, event: PreviewEvent) -> None:
        self._event = event

    async def list_events_for_recipients(
        self,
        *,
        event_type: EventType,
        learner_ids: tuple[int, ...],
        included_package_ids: tuple[int, ...] | None = None,
        excluded_package_ids: tuple[int, ...] = (),
        horizon_days: int,
        limit: int,
        offset: int = 0,
    ) -> tuple[PreviewEvent, ...]:
        if event_type != self._event.event_type:
            return ()
        if self._event.learner_id not in set(learner_ids):
            return ()
        package_id = (
            self._event.event_id
            if self._event.event_type == EventType.PACKAGE
            else self._event.metadata.get("package_id")
        )
        if included_package_ids is not None and package_id not in included_package_ids:
            return ()
        if package_id in excluded_package_ids:
            return ()
        if offset > 0:
            return ()
        return (self._event,)

    async def get_event(self, *, event_type: EventType, event_id: int) -> PreviewEvent | None:
        if self._event.event_type == event_type and self._event.event_id == event_id:
            return self._event
        return None


class _ScopedEventUnitOfWork:
    def __init__(self, source: NotificationMaterializationUnitOfWork, event: PreviewEvent) -> None:
        self.audience_resolver = source.audience_resolver
        self.events: EventRepository = _SingleEventRepository(event)
        self.preferences = source.preferences
        self.rules = source.rules
        self.instances = source.instances
        self.jobs = source.jobs
        self.responses = source.responses
        self.groups = source.groups
        self.templates = source.templates
        self.settings = source.settings

    async def commit(self) -> None:
        raise RuntimeError("Scoped reconciliation unit of work must not commit")


class _LearnerScopedAudienceResolver:
    def __init__(self, source: AudienceResolver, learner_ids: tuple[int, ...]) -> None:
        self._source = source
        self._learner_ids = set(learner_ids)

    async def resolve_recipients(
        self,
        assignments: tuple[AudienceSelector, ...],
    ) -> tuple[PreviewRecipient, ...]:
        recipients = await self._source.resolve_recipients(assignments)
        return tuple(
            recipient
            for recipient in recipients
            if recipient.learner_id in self._learner_ids
        )


class _LearnerScopedAudienceUnitOfWork:
    def __init__(self, source: NotificationMaterializationUnitOfWork, learner_ids: tuple[int, ...]) -> None:
        self.audience_resolver = _LearnerScopedAudienceResolver(source.audience_resolver, learner_ids)
        self.events = source.events
        self.preferences = source.preferences
        self.rules = source.rules
        self.instances = source.instances
        self.jobs = source.jobs
        self.responses = source.responses
        self.groups = source.groups
        self.templates = source.templates
        self.settings = source.settings

    async def commit(self) -> None:
        raise RuntimeError("Scoped reconciliation unit of work must not commit")
