from __future__ import annotations

from notifications.application.dto import (
    AudienceSelector,
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
    PreviewRecipient,
)
from notifications.application.materialization import _materialize_rules
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.domain.enums import NotificationSystemMode


class GetNotificationSettingsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> NotificationSettingsRecord:
        return await self._uow.settings.get_settings()


class UpdateNotificationSettingsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: NotificationSettingsUpdateDraft) -> NotificationSettingsRecord:
        if draft.mode == NotificationSystemMode.NEW and not draft.confirm_global_new:
            raise ValueError("Enabling the new notification system globally requires explicit confirmation")
        settings = await self._uow.settings.update_settings(draft)
        await self._uow.commit()
        return settings


class ListLearnerNotificationModesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[LearnerNotificationModeRecord, ...]:
        return await self._uow.settings.list_learner_modes()


class GetLearnerNotificationModeUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, learner_id: int) -> LearnerNotificationModeRecord | None:
        return await self._uow.settings.get_learner_mode(learner_id)


class SetLearnerNotificationModeUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        learner_id: int,
        draft: LearnerNotificationModeUpdateDraft,
    ) -> LearnerNotificationModeRecord | None:
        mode = await self._uow.settings.set_learner_mode(learner_id, draft)
        if mode is not None:
            await _rebuild_queue_for_learner_mode(self._uow, mode)
        await self._uow.commit()
        return mode


async def _rebuild_queue_for_learner_mode(
    uow: NotificationMaterializationUnitOfWork,
    mode: LearnerNotificationModeRecord,
) -> None:
    rules = await uow.rules.list_active_rules()
    rule_ids = tuple(
        sorted(
            int(rule.rule_id)
            for rule in rules
            if isinstance(rule.rule_id, int)
        )
    )
    if rule_ids:
        await uow.instances.cancel_future_instances_for_rules_and_learners(
            rule_ids=rule_ids,
            learner_ids=(mode.learner_id,),
            reason="learner_notification_mode_changed",
        )

    if mode.effective_mode == NotificationSystemMode.LEGACY or not rules:
        return

    await _materialize_rules(
        _LearnerScopedMaterializationUnitOfWork(uow, mode.learner_id),
        rules,
        horizon_days=30,
        limit=100,
        delivery_enabled=mode.effective_mode == NotificationSystemMode.NEW,
        shadow=mode.effective_mode == NotificationSystemMode.SHADOW,
        commit=False,
        respect_rollout_modes=False,
    )


class _LearnerScopedAudienceResolver:
    def __init__(self, source, learner_id: int) -> None:
        self._source = source
        self._learner_id = learner_id

    async def resolve_recipients(
        self,
        assignments: tuple[AudienceSelector, ...],
    ) -> tuple[PreviewRecipient, ...]:
        recipients = await self._source.resolve_recipients(assignments)
        return tuple(
            recipient
            for recipient in recipients
            if recipient.learner_id == self._learner_id
        )


class _LearnerScopedMaterializationUnitOfWork:
    def __init__(self, source: NotificationMaterializationUnitOfWork, learner_id: int) -> None:
        self.audience_resolver = _LearnerScopedAudienceResolver(source.audience_resolver, learner_id)
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
        raise RuntimeError("Learner-scoped notification mode rebuild must not commit")
