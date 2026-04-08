from __future__ import annotations

from datetime import datetime

from notifications.application.dto import NotificationActivityRecord, NotificationInstanceRecord
from notifications.application.audit import record_notification_audit
from notifications.application.ports import NotificationMaterializationUnitOfWork
from notifications.domain.enums import EventType, InstanceStatus


class ListNotificationInstancesUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        status: InstanceStatus | None = None,
        learner_id: int | None = None,
        event_type: EventType | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        limit: int = 100,
    ) -> tuple[NotificationInstanceRecord, ...]:
        return await self._uow.instances.list_instances(
            status=status.value if status is not None else None,
            learner_id=learner_id,
            event_type=event_type,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            limit=limit,
        )


class GetNotificationInstanceUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, instance_id: int) -> NotificationInstanceRecord | None:
        return await self._uow.instances.get_instance(instance_id)


class ListNotificationActivityUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        learner_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationActivityRecord, ...]:
        return await self._uow.instances.list_activity(
            learner_id=learner_id,
            limit=limit,
        )


class CancelNotificationInstanceUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        instance_id: int,
        *,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> NotificationInstanceRecord | None:
        before = await self._uow.instances.get_instance(instance_id)
        instance = await self._uow.instances.cancel_instance(
            instance_id,
            reason=reason,
        )
        if instance is not None:
            await record_notification_audit(
                self._uow,
                entity_type="notification_instance",
                entity_id=instance.instance_id,
                action="cancelled",
                actor_user_id=actor_user_id,
                before=before,
                after=instance,
                reason=reason,
            )
        await self._uow.commit()
        return instance


class ScheduleNotificationInstanceNowUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        instance_id: int,
        *,
        now: datetime,
        actor_user_id: int | None = None,
    ) -> NotificationInstanceRecord | None:
        before = await self._uow.instances.get_instance(instance_id)
        instance = await self._uow.instances.schedule_instance_now(
            instance_id,
            now=now,
        )
        if instance is not None:
            await record_notification_audit(
                self._uow,
                entity_type="notification_instance",
                entity_id=instance.instance_id,
                action="send_now_scheduled",
                actor_user_id=actor_user_id,
                before=before,
                after=instance,
            )
        await self._uow.commit()
        return instance
