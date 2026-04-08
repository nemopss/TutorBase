from dataclasses import dataclass

import pytest

from notifications.application.dto import (
    LearnerNotificationModeRecord,
    LearnerNotificationModeUpdateDraft,
    NotificationSettingsRecord,
    NotificationSettingsUpdateDraft,
)
from notifications.application.settings import (
    GetLearnerNotificationModeUseCase,
    GetNotificationSettingsUseCase,
    ListLearnerNotificationModesUseCase,
    SetLearnerNotificationModeUseCase,
    UpdateNotificationSettingsUseCase,
)
from notifications.domain.enums import NotificationSystemMode


@dataclass
class FakeSettingsRepository:
    settings: NotificationSettingsRecord
    learner_modes: tuple[LearnerNotificationModeRecord, ...] = ()
    updated_settings: NotificationSettingsUpdateDraft | None = None
    updated_learner_mode: tuple[int, LearnerNotificationModeUpdateDraft] | None = None

    async def get_settings(self):
        return self.settings

    async def update_settings(self, draft):
        self.updated_settings = draft
        return NotificationSettingsRecord(tenant_id=1, mode=draft.mode or self.settings.mode)

    async def list_learner_modes(self):
        return self.learner_modes

    async def get_learner_mode(self, learner_id):
        return next((mode for mode in self.learner_modes if mode.learner_id == learner_id), None)

    async def set_learner_mode(self, learner_id, draft):
        self.updated_learner_mode = (learner_id, draft)
        return LearnerNotificationModeRecord(
            learner_id=learner_id,
            display_name="Вика",
            mode_override=draft.mode_override,
            effective_mode=draft.mode_override,
        )


@dataclass
class FakeUnitOfWork:
    settings: FakeSettingsRepository
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_get_and_update_settings_use_cases():
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.LEGACY)
    )
    uow = FakeUnitOfWork(settings=repository)
    draft = NotificationSettingsUpdateDraft(mode=NotificationSystemMode.SHADOW)

    current = await GetNotificationSettingsUseCase(uow).execute()
    updated = await UpdateNotificationSettingsUseCase(uow).execute(draft)

    assert current.mode == NotificationSystemMode.LEGACY
    assert updated.mode == NotificationSystemMode.SHADOW
    assert repository.updated_settings == draft
    assert uow.committed is True


@pytest.mark.asyncio
async def test_update_settings_requires_explicit_confirmation_for_global_new():
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW)
    )
    uow = FakeUnitOfWork(settings=repository)

    with pytest.raises(ValueError, match="requires explicit confirmation"):
        await UpdateNotificationSettingsUseCase(uow).execute(
            NotificationSettingsUpdateDraft(mode=NotificationSystemMode.NEW)
        )

    assert repository.updated_settings is None
    assert uow.committed is False


@pytest.mark.asyncio
async def test_learner_mode_use_cases():
    mode = LearnerNotificationModeRecord(
        learner_id=10,
        display_name="Вика",
        mode_override=NotificationSystemMode.INHERIT,
        effective_mode=NotificationSystemMode.SHADOW,
    )
    repository = FakeSettingsRepository(
        settings=NotificationSettingsRecord(tenant_id=1, mode=NotificationSystemMode.SHADOW),
        learner_modes=(mode,),
    )
    uow = FakeUnitOfWork(settings=repository)

    listed = await ListLearnerNotificationModesUseCase(uow).execute()
    fetched = await GetLearnerNotificationModeUseCase(uow).execute(10)
    updated = await SetLearnerNotificationModeUseCase(uow).execute(
        learner_id=10,
        draft=LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )

    assert listed == (mode,)
    assert fetched == mode
    assert updated is not None
    assert updated.effective_mode == NotificationSystemMode.NEW
    assert repository.updated_learner_mode == (
        10,
        LearnerNotificationModeUpdateDraft(mode_override=NotificationSystemMode.NEW),
    )
    assert uow.committed is True
