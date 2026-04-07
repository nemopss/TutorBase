from __future__ import annotations

from notifications.application.dto import (
    CombinedPreviewInstance,
    InstanceUpsertResult,
    MaterializeActiveRulesResult,
    MaterializeRulesResult,
    NotificationJobDraft,
    NotificationJobRecord,
    NotificationInstanceComponentDraft,
    NotificationInstanceDraft,
    NotificationRuleDraft,
    PreviewInstance,
)
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.application.preview import PreviewRulesUseCase
from notifications.domain.enums import InstanceStatus


class MaterializeRulesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        drafts: tuple[NotificationRuleDraft, ...],
        *,
        horizon_days: int = 30,
        limit: int = 100,
        delivery_enabled: bool = True,
        shadow: bool = False,
    ) -> MaterializeRulesResult:
        return await _materialize_rules(
            self._uow,
            drafts,
            horizon_days=horizon_days,
            limit=limit,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
            commit=True,
        )


class MaterializeActiveRulesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        horizon_days: int = 30,
        limit: int = 100,
        delivery_enabled: bool = True,
        shadow: bool = False,
        created_by_user_id: int | None = None,
    ) -> MaterializeActiveRulesResult:
        job = await self._uow.jobs.create_job(
            NotificationJobDraft(
                job_type="materialize_active_rules",
                scope={
                    "horizon_days": horizon_days,
                    "limit": limit,
                    "delivery_enabled": delivery_enabled,
                    "shadow": shadow,
                },
                created_by_user_id=created_by_user_id,
            )
        )
        job = await self._uow.jobs.mark_running(job.job_id)
        rules = await self._uow.rules.list_active_rules()
        materialization = await _materialize_rules(
            self._uow,
            rules,
            horizon_days=horizon_days,
            limit=limit,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
            commit=False,
        )
        job = await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "rules_count": len(rules),
                "planned_count": materialization.upsert_result.planned_count,
                "upserted_count": materialization.upsert_result.upserted_count,
                "warnings": list(materialization.warnings),
            },
        )
        await self._uow.commit()
        return MaterializeActiveRulesResult(
            job=job,
            materialization=materialization,
        )


class RunMaterializeActiveRulesJobUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, job: NotificationJobRecord) -> MaterializeActiveRulesResult:
        if job.job_type != "materialize_active_rules":
            raise ValueError(f"Unsupported notification job type: {job.job_type}")
        if job.status != "running":
            raise ValueError(f"Notification job {job.job_id} is not running")

        rules = await self._uow.rules.list_active_rules()
        materialization = await _materialize_rules(
            self._uow,
            rules,
            horizon_days=int(job.scope.get("horizon_days", 30)),
            limit=int(job.scope.get("limit", 100)),
            delivery_enabled=bool(job.scope.get("delivery_enabled", True)),
            shadow=bool(job.scope.get("shadow", False)),
            commit=False,
        )
        succeeded = await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "rules_count": len(rules),
                "planned_count": materialization.upsert_result.planned_count,
                "upserted_count": materialization.upsert_result.upserted_count,
                "warnings": list(materialization.warnings),
            },
        )
        await self._uow.commit()
        return MaterializeActiveRulesResult(job=succeeded, materialization=materialization)


async def _materialize_rules(
    uow: NotificationMaterializationUnitOfWork,
    drafts: tuple[NotificationRuleDraft, ...],
    *,
    horizon_days: int,
    limit: int,
    delivery_enabled: bool,
    shadow: bool,
    commit: bool,
) -> MaterializeRulesResult:
    preview = await PreviewRulesUseCase(uow).execute(
        drafts,
        horizon_days=horizon_days,
        limit=limit,
    )
    template_key_by_rule = {draft.rule_id: draft.template_key for draft in drafts}
    planned = tuple(
        _planned_instance(
            instance,
            template_key_by_rule=template_key_by_rule,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
        for instance in preview.instances
    )
    if not planned:
        return MaterializeRulesResult(
            planned_instances=(),
            upsert_result=InstanceUpsertResult(planned_count=0),
            warnings=preview.warnings,
        )

    upsert_result = await uow.instances.upsert_planned_instances(planned)
    if commit:
        await uow.commit()
    return MaterializeRulesResult(
        planned_instances=planned,
        upsert_result=upsert_result,
        warnings=preview.warnings,
    )


def _planned_instance(
    instance: PreviewInstance | CombinedPreviewInstance,
    *,
    template_key_by_rule: dict[int | str, str | None],
    delivery_enabled: bool,
    shadow: bool,
) -> NotificationInstanceDraft:
    if isinstance(instance, CombinedPreviewInstance):
        status = InstanceStatus.SHADOW if shadow else InstanceStatus.SCHEDULED
        component_drafts = tuple(
            NotificationInstanceComponentDraft(
                rule_id=component.rule_id,
                category=component.category,
                component_key=_component_key(component, template_key_by_rule),
                template_key=template_key_by_rule.get(component.rule_id),
                metadata={
                    "event_type": component.event_type.value,
                    "event_id": component.event_id,
                    "scheduled_for": component.scheduled_for.isoformat(),
                    "effective_scheduled_for": component.effective_scheduled_for.isoformat(),
                },
            )
            for component in instance.components
        )
        return NotificationInstanceDraft(
            rule_id=None,
            category=instance.components[0].category,
            event_type=instance.event_type,
            event_id=instance.event_id,
            event_key=_event_key(instance.event_type.value, instance.event_id),
            recipient_type="learner",
            recipient_id=instance.learner_id,
            learner_id=instance.learner_id,
            scheduled_for=instance.scheduled_for,
            effective_scheduled_for=instance.effective_scheduled_for,
            status=status,
            delivery_enabled=delivery_enabled and status == InstanceStatus.SCHEDULED,
            priority=instance.priority,
            channel="telegram",
            dedupe_key=_combined_dedupe_key(instance, template_key_by_rule),
            combination_key=instance.combination_key,
            explanation={
                "reason": "combined",
                "component_count": len(instance.components),
                "component_rule_ids": [component.rule_id for component in instance.components],
                "warnings": list(instance.warnings),
                "component_explanations": [component.explanation for component in instance.components],
            },
            components=component_drafts,
        )

    status = _status_from_preview(instance, shadow=shadow)
    template_key = template_key_by_rule.get(instance.rule_id)
    return NotificationInstanceDraft(
        rule_id=instance.rule_id,
        category=instance.category,
        event_type=instance.event_type,
        event_id=instance.event_id,
        event_key=_event_key(instance.event_type.value, instance.event_id),
        recipient_type="learner",
        recipient_id=instance.learner_id,
        learner_id=instance.learner_id,
        scheduled_for=instance.scheduled_for,
        effective_scheduled_for=instance.effective_scheduled_for,
        status=status,
        delivery_enabled=delivery_enabled and status == InstanceStatus.SCHEDULED,
        priority=instance.priority,
        channel="telegram",
        dedupe_key=_single_dedupe_key(instance, template_key),
        status_reason=None if instance.reason == "scheduled" else instance.reason,
        explanation=instance.explanation,
    )


def _status_from_preview(instance: PreviewInstance, *, shadow: bool) -> InstanceStatus:
    if instance.status == "skipped":
        return InstanceStatus.SKIPPED
    if shadow:
        return InstanceStatus.SHADOW
    return InstanceStatus.SCHEDULED


def _single_dedupe_key(instance: PreviewInstance, template_key: str | None) -> str:
    message_identity = template_key or f"rule:{instance.rule_id}"
    return "|".join(
        (
            "single",
            instance.category.value,
            str(message_identity),
            instance.effective_scheduled_for.isoformat(),
        )
    )


def _combined_dedupe_key(
    instance: CombinedPreviewInstance,
    template_key_by_rule: dict[int | str, str | None],
) -> str:
    component_keys = ",".join(
        _component_key(component, template_key_by_rule) for component in instance.components
    )
    return "|".join(
        (
            "combined",
            instance.combination_key,
            component_keys,
            instance.effective_scheduled_for.isoformat(),
        )
    )


def _component_key(
    component: PreviewInstance,
    template_key_by_rule: dict[int | str, str | None],
) -> str:
    template_key = template_key_by_rule.get(component.rule_id)
    message_identity = template_key or f"rule:{component.rule_id}"
    return f"{component.category.value}:{message_identity}"


def _event_key(event_type: str, event_id: int | None) -> str:
    if event_id is None:
        return f"{event_type}:none"
    return f"{event_type}:{event_id}"
