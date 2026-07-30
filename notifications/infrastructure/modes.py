from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from notifications.domain.enums import NotificationSystemMode
from notifications.infrastructure.models import LearnerNotificationMode, NotificationSystemSetting


class SqlAlchemyNotificationModeResolver:
    def __init__(self, session: AsyncSession, *, tenant_id: int) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def effective_mode_for_learner(self, learner_id: int) -> NotificationSystemMode:
        learner_mode = await self._learner_mode_override(learner_id)
        if learner_mode and learner_mode != NotificationSystemMode.INHERIT:
            return learner_mode
        return await self._tenant_mode()

    async def _learner_mode_override(self, learner_id: int) -> NotificationSystemMode | None:
        result = await self._session.execute(
            select(LearnerNotificationMode.mode_override).where(
                LearnerNotificationMode.tenant_id == self._tenant_id,
                LearnerNotificationMode.learner_id == learner_id,
            )
        )
        mode = result.scalar_one_or_none()
        return NotificationSystemMode(mode) if mode else None

    async def _tenant_mode(self) -> NotificationSystemMode:
        result = await self._session.execute(
            select(NotificationSystemSetting.mode).where(
                NotificationSystemSetting.tenant_id == self._tenant_id
            )
        )
        mode = result.scalar_one_or_none()
        return NotificationSystemMode(mode) if mode else NotificationSystemMode.LEGACY


async def should_suppress_legacy_reminder_for_learner(
    session: AsyncSession,
    *,
    tenant_id: int,
    learner_id: int,
) -> bool:
    # Keep the proven legacy path alive if the deployment cannot process or
    # deliver new-system jobs. This also protects tenants that were already in
    # NEW mode before automation was disabled by configuration.
    if not config.NOTIFICATIONS_AUTOMATION_ENABLED:
        return False
    mode = await SqlAlchemyNotificationModeResolver(
        session,
        tenant_id=tenant_id,
    ).effective_mode_for_learner(learner_id)
    return mode == NotificationSystemMode.NEW
