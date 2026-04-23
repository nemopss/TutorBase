from __future__ import annotations

from notifications.application.dto import (
    CombinedPreviewInstance,
    NotificationRuleDraft,
    PreviewInstance,
    RulePreviewResult,
)
from notifications.application.ports import NotificationPreviewUnitOfWork
from notifications.domain.combination import combine_lesson_confirmation_and_homework, dedupe_exact
from notifications.domain.eligibility import EligibilityContext, evaluate_eligibility
from notifications.domain.entities import NotificationCandidate, NotificationEvent, NotificationTrigger
from notifications.domain.preferences import resolve_effective_preferences
from notifications.domain.scheduling import apply_quiet_hours, compute_trigger_time
from notifications.domain.templates import validate_template_body
from notifications.domain.enums import EventType


class PreviewRuleUseCase:
    def __init__(self, uow: NotificationPreviewUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        draft: NotificationRuleDraft,
        *,
        horizon_days: int = 30,
        limit: int = 20,
        event_offset: int = 0,
    ) -> RulePreviewResult:
        warnings: list[str] = []
        if draft.template_body:
            validation = validate_template_body(draft.template_body)
            if validation.unknown_variables:
                warnings.append(f"unknown_template_variables:{','.join(validation.unknown_variables)}")

        recipients = await self._uow.audience_resolver.resolve_recipients(draft.assignments)
        if not recipients:
            return RulePreviewResult(instances=(), warnings=("empty_audience", *warnings))

        recipient_by_id = {recipient.learner_id: recipient for recipient in recipients}
        events = await self._uow.events.list_events_for_recipients(
            event_type=draft.event_type,
            learner_ids=tuple(recipient_by_id),
            horizon_days=horizon_days,
            limit=limit,
            offset=event_offset,
        )
        if not events:
            return RulePreviewResult(instances=(), warnings=("no_matching_events", *warnings))
        has_more = len(events) == limit

        global_preference = await self._uow.preferences.get_global_preference()
        preview_instances: list[PreviewInstance] = []
        candidates: list[NotificationCandidate] = []
        instance_by_candidate_key: dict[tuple[object, ...], PreviewInstance] = {}

        for event in events:
            recipient = recipient_by_id.get(event.learner_id)
            if recipient is None:
                continue

            learner_preference = await self._uow.preferences.get_learner_preference(recipient.learner_id)
            group_preferences = await self._uow.preferences.get_group_preferences_for_learner(recipient.learner_id)
            effective_preferences = resolve_effective_preferences(
                global_preference,
                group_preferences=group_preferences,
                learner_preference=learner_preference,
                default_timezone=recipient.timezone,
            )

            eligibility = evaluate_eligibility(
                EligibilityContext(
                    event_type=event.event_type,
                    category=draft.category,
                    recipient_has_contact=recipient.has_contact,
                    learner_notifications_enabled=recipient.notifications_enabled,
                    preferences=effective_preferences,
                    package_status=event.package_status,
                    lesson_status=event.lesson_status,
                    has_homework=event.has_homework,
                )
            )
            if not eligibility.eligible:
                event_warnings = _event_warnings(event)
                preview_instances.append(
                    PreviewInstance(
                        rule_id=draft.rule_id,
                        learner_id=recipient.learner_id,
                        event_type=event.event_type,
                        event_id=event.event_id,
                        category=draft.category,
                        scheduled_for=event.starts_at,
                        effective_scheduled_for=event.starts_at,
                        priority=draft.priority,
                        status="skipped",
                        reason=eligibility.reason,
                        warnings=(*eligibility.warnings, *event_warnings),
                        explanation=_explanation(draft, event, recipient, eligibility.reason),
                    )
                )
                continue

            scheduled_for = compute_trigger_time(
                NotificationTrigger(draft.trigger_type, draft.trigger_config),
                NotificationEvent(
                    event_type=event.event_type,
                    event_id=event.event_id,
                    starts_at=event.starts_at,
                    ends_at=event.ends_at,
                    timezone=event.timezone,
                    metadata=event.metadata,
                ),
            )
            effective_scheduled_for, shifted = apply_quiet_hours(
                scheduled_for,
                effective_preferences.quiet_hours,
                timezone_name=effective_preferences.timezone,
            )
            instance_warnings = list(eligibility.warnings)
            if shifted:
                instance_warnings.append("quiet_hours_shifted")
            instance_warnings.extend(_event_warnings(event))

            preview = PreviewInstance(
                rule_id=draft.rule_id,
                learner_id=recipient.learner_id,
                event_type=event.event_type,
                event_id=event.event_id,
                category=draft.category,
                scheduled_for=scheduled_for,
                effective_scheduled_for=effective_scheduled_for,
                priority=draft.priority,
                status="scheduled",
                warnings=tuple(instance_warnings),
                explanation=_explanation(draft, event, recipient, "eligible"),
            )
            preview_instances.append(preview)
            candidate = NotificationCandidate(
                rule_id=draft.rule_id,
                category=draft.category,
                event_type=event.event_type,
                event_id=event.event_id,
                learner_id=recipient.learner_id,
                scheduled_for=effective_scheduled_for,
                priority=draft.priority,
                template_key=draft.template_key,
            )
            candidates.append(candidate)
            instance_by_candidate_key[candidate.exact_dedupe_key] = preview

        deduped_candidates = dedupe_exact(candidates)
        combined_candidates = combine_lesson_confirmation_and_homework(deduped_candidates)
        scheduled_results: list[PreviewInstance | CombinedPreviewInstance] = []
        consumed_keys: set[tuple[object, ...]] = set()
        for candidate in combined_candidates:
            if isinstance(candidate, NotificationCandidate):
                preview = instance_by_candidate_key[candidate.exact_dedupe_key]
                scheduled_results.append(preview)
                consumed_keys.add(candidate.exact_dedupe_key)
                continue

            component_previews = tuple(
                instance_by_candidate_key[component.exact_dedupe_key]
                for component in candidate.components
            )
            scheduled_results.append(
                CombinedPreviewInstance(
                    combination_key=candidate.combination_key,
                    learner_id=int(candidate.learner_id),
                    event_type=candidate.event_type,
                    event_id=int(candidate.event_id) if candidate.event_id is not None else None,
                    scheduled_for=component_previews[0].scheduled_for,
                    effective_scheduled_for=candidate.scheduled_for,
                    priority=candidate.priority,
                    components=component_previews,
                    warnings=tuple(dict.fromkeys(("combined", *_component_warnings(component_previews)))),
                )
            )
            consumed_keys.update(component.exact_dedupe_key for component in candidate.components)

        skipped_results = [
            instance
            for instance in preview_instances
            if instance.status != "scheduled" or (
                instance.status == "scheduled"
                and _candidate_key_from_preview(instance, draft.template_key) not in consumed_keys
                and _candidate_key_from_preview(instance, draft.template_key) not in {
                    candidate.exact_dedupe_key for candidate in deduped_candidates
                }
            )
        ]
        return RulePreviewResult(
            instances=tuple([*scheduled_results, *skipped_results][:limit]),
            warnings=tuple(warnings),
            has_more=has_more,
        )


class PreviewRulesUseCase:
    def __init__(self, uow: NotificationPreviewUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        drafts: tuple[NotificationRuleDraft, ...],
        *,
        horizon_days: int = 30,
        limit: int = 20,
    ) -> RulePreviewResult:
        single_rule_use_case = PreviewRuleUseCase(self._uow)
        rule_results: list[RulePreviewResult] = []
        for draft in drafts:
            rule_results.append(
                await single_rule_use_case.execute(draft, horizon_days=horizon_days, limit=limit)
            )
        return _combine_rule_results(
            rule_results=tuple(rule_results),
            template_key_by_rule={
                draft.rule_id: draft.template_key for draft in drafts
            },
            limit=limit,
        )

    async def execute_all(
        self,
        drafts: tuple[NotificationRuleDraft, ...],
        *,
        horizon_days: int = 30,
        page_size: int = 100,
    ) -> RulePreviewResult:
        single_rule_use_case = PreviewRuleUseCase(self._uow)
        rule_results: list[RulePreviewResult] = []
        for draft in drafts:
            event_offset = 0
            while True:
                result = await single_rule_use_case.execute(
                    draft,
                    horizon_days=horizon_days,
                    limit=page_size,
                    event_offset=event_offset,
                )
                if not result.instances and event_offset > 0:
                    break
                if not result.instances and not result.has_more:
                    rule_results.append(result)
                    break
                rule_results.append(result)
                if not result.has_more:
                    break
                event_offset += page_size

        return _combine_rule_results(
            rule_results=tuple(rule_results),
            template_key_by_rule={
                draft.rule_id: draft.template_key for draft in drafts
            },
            limit=None,
        )


def _combine_rule_results(
    *,
    rule_results: tuple[RulePreviewResult, ...],
    template_key_by_rule: dict[int | str, str | None],
    limit: int | None,
) -> RulePreviewResult:
    warnings: list[str] = []
    scheduled: list[PreviewInstance] = []
    passthrough: list[PreviewInstance | CombinedPreviewInstance] = []
    for result in rule_results:
        warnings.extend(result.warnings)
        for instance in result.instances:
            if isinstance(instance, PreviewInstance) and instance.status == "scheduled":
                scheduled.append(instance)
            else:
                passthrough.append(instance)

    candidate_by_key: dict[tuple[object, ...], NotificationCandidate] = {}
    instance_by_key: dict[tuple[object, ...], PreviewInstance] = {}
    for instance in scheduled:
        candidate = NotificationCandidate(
            rule_id=instance.rule_id,
            category=instance.category,
            event_type=instance.event_type,
            event_id=instance.event_id,
            learner_id=instance.learner_id,
            scheduled_for=instance.effective_scheduled_for,
            priority=instance.priority,
            template_key=template_key_by_rule.get(instance.rule_id),
        )
        candidate_by_key.setdefault(candidate.exact_dedupe_key, candidate)
        instance_by_key.setdefault(candidate.exact_dedupe_key, instance)

    combined_candidates = combine_lesson_confirmation_and_homework(list(candidate_by_key.values()))
    combined_results: list[PreviewInstance | CombinedPreviewInstance] = []
    consumed_keys: set[tuple[object, ...]] = set()
    for candidate in combined_candidates:
        if isinstance(candidate, NotificationCandidate):
            combined_results.append(instance_by_key[candidate.exact_dedupe_key])
            consumed_keys.add(candidate.exact_dedupe_key)
            continue

        component_previews = tuple(
            instance_by_key[component.exact_dedupe_key]
            for component in candidate.components
        )
        combined_results.append(
            CombinedPreviewInstance(
                combination_key=candidate.combination_key,
                learner_id=int(candidate.learner_id),
                event_type=candidate.event_type,
                event_id=int(candidate.event_id) if candidate.event_id is not None else None,
                scheduled_for=component_previews[0].scheduled_for,
                effective_scheduled_for=candidate.scheduled_for,
                priority=candidate.priority,
                components=component_previews,
                warnings=tuple(dict.fromkeys(("combined", *_component_warnings(component_previews)))),
            )
        )
        consumed_keys.update(component.exact_dedupe_key for component in candidate.components)

    instances = tuple([*combined_results, *passthrough]) if limit is None else tuple([*combined_results, *passthrough][:limit])
    return RulePreviewResult(
        instances=instances,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _explanation(draft, event, recipient, reason: str) -> dict:
    explanation = {
        "rule_id": draft.rule_id,
        "rule_name": draft.name,
        "learner_id": recipient.learner_id,
        "learner_name": recipient.display_name,
        "event_type": event.event_type.value,
        "event_id": event.event_id,
        "event_starts_at": event.starts_at.isoformat() if event.starts_at is not None else None,
        "event_ends_at": event.ends_at.isoformat() if event.ends_at is not None else None,
        "event_timezone": event.timezone,
        "reason": reason,
    }
    calendar_conflict = _calendar_conflict_metadata(event)
    if calendar_conflict is not None:
        explanation["calendar_conflict"] = calendar_conflict
    return explanation


def _event_warnings(event) -> tuple[str, ...]:
    if _calendar_conflict_metadata(event) is not None:
        return ("calendar_conflict:active_lessons_same_slot",)
    return ()


def _calendar_conflict_metadata(event) -> dict | None:
    conflict_count = int(event.metadata.get("calendar_conflict_count") or 0)
    if event.event_type != EventType.LESSON:
        return None
    if conflict_count <= 1:
        return None
    return {
        "type": "active_lessons_same_slot",
        "count": conflict_count,
        "lesson_ids": list(event.metadata.get("calendar_conflict_lesson_ids") or ()),
        "package_ids": list(event.metadata.get("calendar_conflict_package_ids") or ()),
    }


def _component_warnings(components: tuple[PreviewInstance, ...]) -> tuple[str, ...]:
    return tuple(
        warning
        for component in components
        for warning in component.warnings
    )


def _candidate_key_from_preview(instance: PreviewInstance, template_key: str | None) -> tuple[object, ...]:
    return (
        instance.learner_id,
        instance.event_type,
        instance.event_id,
        instance.category,
        template_key,
        instance.effective_scheduled_for,
    )
