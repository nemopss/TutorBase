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
from notifications.domain.enums import EventType, InstanceStatus


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
        delivery_grace_seconds: int = 0,
    ) -> ClaimDueNotificationsResult:
        claim_time = now or datetime.now(timezone.utc)
        result = await self._uow.instances.claim_due_instances(
            now=claim_time,
            limit=limit,
            lease_seconds=lease_seconds,
            delivery_grace_seconds=delivery_grace_seconds,
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
        max_attempts: int = 5,
    ) -> None:
        self._uow = uow
        self._renderer = renderer
        self._channel_adapter = channel_adapter
        self._max_attempts = max(1, max_attempts)

    async def execute(
        self,
        instance: ClaimedNotificationInstance,
        *,
        now: datetime | None = None,
    ) -> ExecuteNotificationDeliveryResult:
        try:
            suppressed_at = now or datetime.now(timezone.utc)
            suppression_reason = await _delivery_suppression_reason(self._uow, instance)
            if suppression_reason is not None:
                await self._uow.instances.mark_delivery_suppressed(
                    instance_id=instance.instance_id,
                    attempt_id=instance.attempt_id,
                    reason=suppression_reason,
                    suppressed_at=suppressed_at,
                )
                await self._uow.commit()
                return ExecuteNotificationDeliveryResult(
                    instance_id=instance.instance_id,
                    attempt_id=instance.attempt_id,
                    status=InstanceStatus.SUPPRESSED,
                    error_code=suppression_reason,
                )

            rendered = await self._renderer.render(instance)
            send_result = await self._channel_adapter.send(
                instance=instance,
                rendered=rendered,
            )
        except NotificationDeliveryError as exc:
            failed_at = now or datetime.now(timezone.utc)
            should_retry = exc.retryable and instance.attempt_no < self._max_attempts
            await self._uow.instances.mark_delivery_failed(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                error_code=exc.error_code,
                error_message=str(exc),
                retryable=should_retry,
                failed_at=failed_at,
            )
            await self._uow.commit()
            return ExecuteNotificationDeliveryResult(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                status=InstanceStatus.SCHEDULED if should_retry else InstanceStatus.FAILED,
                error_code=exc.error_code,
                error_message=str(exc),
            )
        except Exception as exc:
            failed_at = now or datetime.now(timezone.utc)
            error_code = exc.__class__.__name__
            should_retry = instance.attempt_no < self._max_attempts
            await self._uow.instances.mark_delivery_failed(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                error_code=error_code,
                error_message=str(exc),
                retryable=should_retry,
                failed_at=failed_at,
            )
            await self._uow.commit()
            return ExecuteNotificationDeliveryResult(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                status=InstanceStatus.SCHEDULED if should_retry else InstanceStatus.FAILED,
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


async def _delivery_suppression_reason(
    uow: NotificationMaterializationUnitOfWork,
    instance: ClaimedNotificationInstance,
) -> str | None:
    if instance.event_type not in {EventType.LESSON, EventType.PACKAGE}:
        return None
    if instance.event_id is None:
        return "delivery_event_missing"

    event = await uow.events.get_event(
        event_type=instance.event_type,
        event_id=instance.event_id,
    )
    if event is None or event.learner_id != instance.learner_id:
        return "delivery_event_not_found"
    if instance.event_type == EventType.LESSON:
        if event.package_status != "active":
            return "delivery_package_not_active"
        if event.lesson_status not in {"scheduled", "rescheduled"}:
            return "delivery_lesson_not_schedulable"
    elif event.package_status != "active":
        return "delivery_package_not_active"
    return None
