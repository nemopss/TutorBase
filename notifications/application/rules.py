from __future__ import annotations

from notifications.application.dto import (
    NotificationRuleCreateDraft,
    NotificationRuleRecord,
    NotificationRuleUpdateDraft,
)
from notifications.application.audit import record_notification_audit
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.domain.enums import RuleStatus


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
        rule = await self._uow.rules.create_rule(draft)
        await record_notification_audit(
            self._uow,
            entity_type="notification_rule",
            entity_id=rule.rule_id,
            action="created",
            actor_user_id=draft.created_by_user_id,
            after=rule,
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
        before = await self._uow.rules.get_rule(rule_id)
        rule = await self._uow.rules.update_rule(rule_id, draft)
        if rule is not None:
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
        rule = await self._uow.rules.set_rule_status(rule_id, RuleStatus.ACTIVE.value)
        if rule is not None:
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
