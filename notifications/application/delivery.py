from __future__ import annotations

from datetime import datetime, timezone

from notifications.application.dto import (
    ClaimedNotificationInstance,
    ClaimDueNotificationsResult,
    ExecuteNotificationDeliveryResult,
)
from notifications.application.ports import (
    NotificationChannelAdapter,
    NotificationMaterializationUnitOfWork,
    NotificationRenderer,
)
from notifications.domain.enums import InstanceStatus


class NotificationDeliveryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__
        self.retryable = retryable


class ClaimDueNotificationsUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
        lease_seconds: int = 300,
    ) -> ClaimDueNotificationsResult:
        claim_time = now or datetime.now(timezone.utc)
        result = await self._uow.instances.claim_due_instances(
            now=claim_time,
            limit=limit,
            lease_seconds=lease_seconds,
        )
        await self._uow.commit()
        return result


class ExecuteClaimedNotificationDeliveryUseCase:
    def __init__(
        self,
        uow: NotificationMaterializationUnitOfWork,
        *,
        renderer: NotificationRenderer,
        channel_adapter: NotificationChannelAdapter,
    ) -> None:
        self._uow = uow
        self._renderer = renderer
        self._channel_adapter = channel_adapter

    async def execute(
        self,
        instance: ClaimedNotificationInstance,
        *,
        now: datetime | None = None,
    ) -> ExecuteNotificationDeliveryResult:
        try:
            rendered = await self._renderer.render(instance)
            send_result = await self._channel_adapter.send(
                instance=instance,
                rendered=rendered,
            )
        except NotificationDeliveryError as exc:
            failed_at = now or datetime.now(timezone.utc)
            await self._uow.instances.mark_delivery_failed(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                error_code=exc.error_code,
                error_message=str(exc),
                retryable=exc.retryable,
                failed_at=failed_at,
            )
            await self._uow.commit()
            return ExecuteNotificationDeliveryResult(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                status=InstanceStatus.SCHEDULED if exc.retryable else InstanceStatus.FAILED,
                error_code=exc.error_code,
                error_message=str(exc),
            )
        except Exception as exc:
            failed_at = now or datetime.now(timezone.utc)
            error_code = exc.__class__.__name__
            await self._uow.instances.mark_delivery_failed(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                error_code=error_code,
                error_message=str(exc),
                retryable=True,
                failed_at=failed_at,
            )
            await self._uow.commit()
            return ExecuteNotificationDeliveryResult(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                status=InstanceStatus.SCHEDULED,
                error_code=error_code,
                error_message=str(exc),
            )

        await self._uow.instances.mark_delivery_sent(
            instance_id=instance.instance_id,
            attempt_id=instance.attempt_id,
            rendered=rendered,
            send_result=send_result,
        )
        await self._uow.commit()
        return ExecuteNotificationDeliveryResult(
            instance_id=instance.instance_id,
            attempt_id=instance.attempt_id,
            status=InstanceStatus.SENT,
            provider_message_id=send_result.provider_message_id,
        )
