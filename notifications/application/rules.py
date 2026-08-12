from __future__ import annotations

from notifications.application.dto import (
    NotificationJobDraft,
    NotificationRuleCreateDraft,
    NotificationRuleRecord,
    NotificationRuleUpdateDraft,
)
from notifications.application.audit import record_notification_audit
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.domain.enums import NotificationSystemMode, RuleStatus
from notifications.domain.templates import validate_template_body


def _validate_inline_template_or_raise(body: str | None) -> None:
    if not body:
        return
    validation = validate_template_body(body)
    if validation.unknown_variables:
        raise ValueError(
            "Unknown template variables: "
            + ", ".join(validation.unknown_variables)
        )


class ListNotificationRulesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, include_archived: bool = False) -> tuple[NotificationRuleRecord, ...]:
        return await self._uow.rules.list_rules(include_archived=include_archived)


class GetNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, rule_id: int) -> NotificationRuleRecord | None:
        return await self._uow.rules.get_rule(rule_id)


class CreateNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: NotificationRuleCreateDraft) -> NotificationRuleRecord:
        _validate_inline_template_or_raise(draft.inline_template_body)
        rule = await self._uow.rules.create_rule(draft)
        await record_notification_audit(
            self._uow,
            entity_type="notification_rule",
            entity_id=rule.rule_id,
            action="created",
            actor_user_id=draft.created_by_user_id,
            after=rule,
        )
        if rule.status == RuleStatus.ACTIVE:
            await _queue_active_rules_rebuild(
                self._uow,
                reason="rule_created_active",
                created_by_user_id=draft.created_by_user_id,
            )
        await self._uow.commit()
        return rule


class UpdateNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        rule_id: int,
        draft: NotificationRuleUpdateDraft,
        actor_user_id: int | None = None,
    ) -> NotificationRuleRecord | None:
        if draft.inline_template_body_set or draft.inline_template_body is not None:
            _validate_inline_template_or_raise(draft.inline_template_body)
        before = await self._uow.rules.get_rule(rule_id)
        rule = await self._uow.rules.update_rule(rule_id, draft)
        if rule is not None:
            await _cancel_future_instances_for_inactive_rule(
                self._uow,
                rule_id=rule.rule_id,
                status=draft.status,
            )
            if rule.status == RuleStatus.ACTIVE:
                await self._uow.instances.cancel_future_instances_for_rules(
                    rule_ids=(rule.rule_id,),
                    reason="rule_updated",
                )
                await _queue_active_rules_rebuild(
                    self._uow,
                    reason="rule_updated",
                    created_by_user_id=actor_user_id,
                )
            await record_notification_audit(
                self._uow,
                entity_type="notification_rule",
                entity_id=rule.rule_id,
                action="updated",
                actor_user_id=actor_user_id,
                before=before,
                after=rule,
            )
        await self._uow.commit()
        return rule


class ActivateNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        rule_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> NotificationRuleRecord | None:
        before = await self._uow.rules.get_rule(rule_id)
        if before is not None:
            _validate_inline_template_or_raise(before.inline_template_body)
        rule = await self._uow.rules.set_rule_status(rule_id, RuleStatus.ACTIVE.value)
        if rule is not None:
            await _queue_active_rules_rebuild(
                self._uow,
                reason="rule_activated",
                created_by_user_id=actor_user_id,
            )
            await record_notification_audit(
                self._uow,
                entity_type="notification_rule",
                entity_id=rule.rule_id,
                action="activated",
                actor_user_id=actor_user_id,
                before=before,
                after=rule,
            )
        await self._uow.commit()
        return rule


class PauseNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        rule_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> NotificationRuleRecord | None:
        before = await self._uow.rules.get_rule(rule_id)
        rule = await self._uow.rules.set_rule_status(rule_id, RuleStatus.PAUSED.value)
        if rule is not None:
            await _cancel_future_instances_for_inactive_rule(
                self._uow,
                rule_id=rule.rule_id,
                status=RuleStatus.PAUSED,
            )
            await record_notification_audit(
                self._uow,
                entity_type="notification_rule",
                entity_id=rule.rule_id,
                action="paused",
                actor_user_id=actor_user_id,
                before=before,
                after=rule,
            )
        await self._uow.commit()
        return rule


class ArchiveNotificationRuleUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        rule_id: int,
        *,
        actor_user_id: int | None = None,
    ) -> NotificationRuleRecord | None:
        before = await self._uow.rules.get_rule(rule_id)
        rule = await self._uow.rules.set_rule_status(rule_id, RuleStatus.ARCHIVED.value)
        if rule is not None:
            await _cancel_future_instances_for_inactive_rule(
                self._uow,
                rule_id=rule.rule_id,
                status=RuleStatus.ARCHIVED,
            )
            await record_notification_audit(
                self._uow,
                entity_type="notification_rule",
                entity_id=rule.rule_id,
                action="archived",
                actor_user_id=actor_user_id,
                before=before,
                after=rule,
            )
        await self._uow.commit()
        return rule


async def _cancel_future_instances_for_inactive_rule(
    uow: NotificationMaterializationUnitOfWork,
    *,
    rule_id: int,
    status: RuleStatus | None,
) -> None:
    if status not in {RuleStatus.DRAFT, RuleStatus.PAUSED, RuleStatus.ARCHIVED}:
        return

    await uow.instances.cancel_future_instances_for_rules(
        rule_ids=(rule_id,),
        reason="rule_not_active",
    )


async def _queue_active_rules_rebuild(
    uow: NotificationMaterializationUnitOfWork,
    *,
    reason: str,
    created_by_user_id: int | None,
) -> None:
    settings = await uow.settings.get_settings()
    delivery_enabled = settings.mode == NotificationSystemMode.NEW
    await uow.jobs.create_job(
        NotificationJobDraft(
            job_type="materialize_active_rules",
            scope={
                "reason": reason,
                "horizon_days": 30,
                "limit": 100,
                "delivery_enabled": delivery_enabled,
                "shadow": not delivery_enabled,
            },
            created_by_user_id=created_by_user_id,
            dedupe_key="materialize_active_rules",
        )
    )
