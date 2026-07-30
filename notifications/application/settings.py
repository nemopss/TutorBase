from __future__ import annotations

from notifications.application.dto import (
    AudienceSelector,
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
    PreviewRecipient,
)
from notifications.application.materialization import (
    _cancel_persisted_instances_for_materialization,
    _materialize_rules,
)
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.domain.enums import NotificationSystemMode


_TENANT_MODE_REBUILD_PAGE_SIZE = 1_000


class GetNotificationSettingsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> NotificationSettingsRecord:
        return await self._uow.settings.get_settings()


class UpdateNotificationSettingsUseCase:
    def __init__(
        self,
        uow: NotificationMaterializationUnitOfWork,
        *,
        automation_enabled: bool = True,
    ) -> None:
        self._uow = uow
        self._automation_enabled = automation_enabled

    async def execute(self, draft: NotificationSettingsUpdateDraft) -> NotificationSettingsRecord:
        current_settings = await self._uow.settings.get_settings()
        if draft.mode == NotificationSystemMode.NEW and not draft.confirm_global_new:
            raise ValueError("Enabling the new notification system globally requires explicit confirmation")
        if draft.mode == NotificationSystemMode.NEW and not self._automation_enabled:
            raise ValueError(
                "The new notification system cannot be enabled while notification automation is disabled"
            )
        settings = await self._uow.settings.update_settings(draft)
        if draft.mode == NotificationSystemMode.NEW and current_settings.mode != NotificationSystemMode.NEW:
            await self._uow.settings.clear_learner_modes()
            await _rebuild_queue_for_tenant_mode(self._uow, settings)
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
            await _rebuild_queue_for_learner_mode(
                self._uow,
                mode,
                reason="learner_notification_mode_changed",
            )
        await self._uow.commit()
        return mode


class RebuildLearnerNotificationQueueUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        learner_id: int,
        reason: str,
        commit: bool = True,
    ) -> LearnerNotificationModeRecord | None:
        mode = await self._uow.settings.get_learner_mode(learner_id)
        if mode is not None:
            await _rebuild_queue_for_learner_mode(
                self._uow,
                mode,
                reason=reason,
            )
        if commit:
            await self._uow.commit()
        return mode


async def _rebuild_queue_for_learner_mode(
    uow: NotificationMaterializationUnitOfWork,
    mode: LearnerNotificationModeRecord,
    *,
    reason: str,
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
            reason=reason,
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
        skip_past_due=True,
    )


async def _rebuild_queue_for_tenant_mode(
    uow: NotificationMaterializationUnitOfWork,
    settings: NotificationSettingsRecord,
) -> None:
    if settings.mode != NotificationSystemMode.NEW:
        return

    rules = await uow.rules.list_active_rules()
    if not rules:
        return

    await _cancel_persisted_instances_for_materialization(
        uow,
        delivery_enabled=True,
        shadow=False,
    )
    await _materialize_rules(
        uow,
        rules,
        horizon_days=30,
        limit=_TENANT_MODE_REBUILD_PAGE_SIZE,
        delivery_enabled=True,
        shadow=False,
        commit=False,
        respect_rollout_modes=False,
        skip_past_due=True,
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
