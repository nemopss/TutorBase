from __future__ import annotations

from datetime import datetime, timezone

from notifications.application.dto import (
    CombinedPreviewInstance,
    InstanceUpsertResult,
    LearnerNotificationModeRecord,
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
from notifications.domain.enums import InstanceStatus, NotificationSystemMode


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
        live_materialization = _is_live_materialization(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
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
        cancelled_count = await _cancel_persisted_instances_for_materialization(
            self._uow,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
        rules = await self._uow.rules.list_active_rules()
        materialization = await _materialize_rules(
            self._uow,
            rules,
            horizon_days=horizon_days,
            limit=limit,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
            commit=False,
            respect_rollout_modes=_should_apply_rollout_modes(
                delivery_enabled=delivery_enabled,
                shadow=shadow,
            ),
            skip_past_due=live_materialization,
        )
        job = await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "rules_count": len(rules),
                "cancelled_count": cancelled_count,
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

        delivery_enabled = bool(job.scope.get("delivery_enabled", True))
        shadow = bool(job.scope.get("shadow", False))
        live_materialization = _is_live_materialization(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
        cancelled_count = await _cancel_persisted_instances_for_materialization(
            self._uow,
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        )
        rules = await self._uow.rules.list_active_rules()
        materialization = await _materialize_rules(
            self._uow,
            rules,
            horizon_days=int(job.scope.get("horizon_days", 30)),
            limit=int(job.scope.get("limit", 100)),
            delivery_enabled=delivery_enabled,
            shadow=shadow,
            commit=False,
            respect_rollout_modes=_should_apply_rollout_modes(
                delivery_enabled=delivery_enabled,
                shadow=shadow,
            ),
            skip_past_due=live_materialization,
        )
        succeeded = await self._uow.jobs.mark_succeeded(
            job.job_id,
            result_summary={
                "rules_count": len(rules),
                "cancelled_count": cancelled_count,
                "planned_count": materialization.upsert_result.planned_count,
                "upserted_count": materialization.upsert_result.upserted_count,
                "warnings": list(materialization.warnings),
            },
        )
        await self._uow.commit()
        return MaterializeActiveRulesResult(job=succeeded, materialization=materialization)


async def _cancel_persisted_instances_for_materialization(
    uow: NotificationMaterializationUnitOfWork,
    *,
    delivery_enabled: bool,
    shadow: bool,
) -> int:
    all_rules = await uow.rules.list_rules(include_archived=True)
    all_rule_ids = tuple(
        sorted(
            int(rule.rule_id)
            for rule in all_rules
            if isinstance(rule.rule_id, int)
        )
    )
    if not all_rule_ids:
        return 0

    return await uow.instances.cancel_future_instances_for_rules(
        rule_ids=all_rule_ids,
        reason=_rematerialization_reason(shadow=shadow),
        statuses=_rematerialization_cancel_statuses(
            delivery_enabled=delivery_enabled,
            shadow=shadow,
        ),
    )


def _should_apply_rollout_modes(*, delivery_enabled: bool, shadow: bool) -> bool:
    return delivery_enabled and not shadow


def _is_live_materialization(*, delivery_enabled: bool, shadow: bool) -> bool:
    return delivery_enabled and not shadow


def _rematerialization_reason(*, shadow: bool) -> str:
    return "rematerialized:shadow_all_rules" if shadow else "rematerialized:all_rules"


def _rematerialization_cancel_statuses(
    *,
    delivery_enabled: bool,
    shadow: bool,
) -> tuple[InstanceStatus, ...] | None:
    if shadow and not delivery_enabled:
        return (InstanceStatus.SHADOW,)
    return None


async def _materialize_rules(
    uow: NotificationMaterializationUnitOfWork,
    drafts: tuple[NotificationRuleDraft, ...],
    *,
    horizon_days: int,
    limit: int,
    delivery_enabled: bool,
    shadow: bool,
    commit: bool,
    respect_rollout_modes: bool = False,
    skip_past_due: bool = False,
) -> MaterializeRulesResult:
    preview = await PreviewRulesUseCase(uow).execute_all(
        drafts,
        horizon_days=horizon_days,
        page_size=max(1, limit),
    )
    preview_instances = preview.instances
    if skip_past_due:
        reference_time = datetime.now(timezone.utc)
        preview_instances = tuple(
            instance
            for instance in preview.instances
            if instance.effective_scheduled_for >= reference_time
        )
    learner_modes = (
        await uow.settings.list_learner_modes()
        if respect_rollout_modes
        else ()
    )
    effective_mode_by_learner = {
        mode.learner_id: mode.effective_mode
        for mode in learner_modes
    }
    template_key_by_rule = {draft.rule_id: draft.template_key for draft in drafts}
    planned = tuple(
        _planned_instance(
            instance,
            template_key_by_rule=template_key_by_rule,
            delivery_enabled=rollout_delivery_enabled,
            shadow=rollout_shadow,
        )
        for instance in preview_instances
        for rollout_delivery_enabled, rollout_shadow in [_resolve_rollout_behavior(
            instance.learner_id,
            effective_mode_by_learner=effective_mode_by_learner,
            default_delivery_enabled=delivery_enabled,
            default_shadow=shadow,
        )]
        if rollout_delivery_enabled is not None
    )
    warnings = _materialization_warnings(
        preview_warnings=preview.warnings,
        preview_instances=preview_instances,
        planned_instances=planned,
        respect_rollout_modes=respect_rollout_modes,
    )
    if not planned:
        return MaterializeRulesResult(
            planned_instances=(),
            upsert_result=InstanceUpsertResult(planned_count=0),
            warnings=warnings,
        )

    upsert_result = await uow.instances.upsert_planned_instances(planned)
    if commit:
        await uow.commit()
    return MaterializeRulesResult(
        planned_instances=planned,
        upsert_result=upsert_result,
        warnings=warnings,
    )


def _resolve_rollout_behavior(
    learner_id: int,
    *,
    effective_mode_by_learner: dict[int, NotificationSystemMode],
    default_delivery_enabled: bool,
    default_shadow: bool,
) -> tuple[bool | None, bool]:
    if not effective_mode_by_learner:
        return default_delivery_enabled, default_shadow

    effective_mode = effective_mode_by_learner.get(learner_id, NotificationSystemMode.LEGACY)
    if effective_mode == NotificationSystemMode.LEGACY:
        return None, True
    if effective_mode == NotificationSystemMode.SHADOW:
        return False, True
    return True, False


def _materialization_warnings(
    *,
    preview_warnings: tuple[str, ...],
    preview_instances: tuple[PreviewInstance | CombinedPreviewInstance, ...],
    planned_instances: tuple[NotificationInstanceDraft, ...],
    respect_rollout_modes: bool,
) -> tuple[str, ...]:
    warnings = list(preview_warnings)
    if respect_rollout_modes and preview_instances and not planned_instances:
        warnings.append("no_rollout_learners_selected")
    return tuple(dict.fromkeys(warnings))


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
        explanation={
            **instance.explanation,
            "warnings": list(instance.warnings),
        },
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
