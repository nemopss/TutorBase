from __future__ import annotations

from notifications.application.dto import (
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
)
from notifications.application.ports import NotificationMaterializationUnitOfWork


class GetNotificationSettingsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> NotificationSettingsRecord:
        return await self._uow.settings.get_settings()


class UpdateNotificationSettingsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: NotificationSettingsUpdateDraft) -> NotificationSettingsRecord:
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
        await self._uow.commit()
        return mode
