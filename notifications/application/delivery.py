from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from notifications.application.dto import (
    AudienceSelector,
    ClaimedNotificationInstance,
    ClaimDueNotificationsResult,
    ExecuteNotificationDeliveryResult,
)
from notifications.application.ports import (
    NotificationChannelAdapter,
    NotificationMaterializationUnitOfWork,
    NotificationRenderer,
)
from notifications.domain.eligibility import EligibilityContext, evaluate_eligibility
from notifications.domain.enums import CapMode, EventType, InstanceStatus
from notifications.domain.enums import NotificationSystemMode
from notifications.domain.preferences import resolve_effective_preferences


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
        delivery_time = now or datetime.now(timezone.utc)
        if not await self._uow.instances.is_delivery_claim_current(
            instance_id=instance.instance_id,
            attempt_id=instance.attempt_id,
            now=delivery_time,
        ):
            return ExecuteNotificationDeliveryResult(
                instance_id=instance.instance_id,
                attempt_id=instance.attempt_id,
                status=InstanceStatus.SUPPRESSED,
                error_code="delivery_claim_expired",
            )
        try:
            suppressed_at = delivery_time
            suppression_reason = await _delivery_suppression_reason(
                self._uow,
                instance,
                delivery_time=delivery_time,
            )
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
    *,
    delivery_time: datetime,
) -> str | None:
    if instance.learner_id is None:
        return "delivery_learner_missing"

    mode = await uow.settings.get_learner_mode(instance.learner_id)
    if mode is None:
        return "delivery_learner_not_found"
    if mode.effective_mode != NotificationSystemMode.NEW:
        return "delivery_mode_not_new"

    recipients = await uow.audience_resolver.resolve_recipients(
        (AudienceSelector(scope_type="learner", scope_id=instance.learner_id),)
    )
    recipient = next(
        (item for item in recipients if item.learner_id == instance.learner_id),
        None,
    )
    if recipient is None:
        return "delivery_learner_not_found"
    if not recipient.has_contact:
        return "missing_contact"
    if not recipient.notifications_enabled:
        return "learner_notifications_disabled"

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
    effective_preferences = resolve_effective_preferences(
        await uow.preferences.get_global_preference(),
        group_preferences=await uow.preferences.get_group_preferences_for_learner(instance.learner_id),
        learner_preference=await uow.preferences.get_learner_preference(instance.learner_id),
        default_timezone=recipient.timezone,
    )
    eligibility = evaluate_eligibility(
        EligibilityContext(
            event_type=event.event_type,
            category=instance.category,
            recipient_has_contact=recipient.has_contact,
            learner_notifications_enabled=recipient.notifications_enabled,
            preferences=effective_preferences,
            package_status=event.package_status,
            lesson_status=event.lesson_status,
            has_homework=event.has_homework,
        )
    )
    if not eligibility.eligible:
        return f"delivery_{eligibility.reason}"
    if effective_preferences.cap_mode == CapMode.ENFORCE:
        try:
            learner_timezone = ZoneInfo(effective_preferences.timezone)
        except Exception:
            learner_timezone = ZoneInfo("Europe/Moscow")
        local_date = delivery_time.astimezone(learner_timezone).date()
        local_start = datetime.combine(local_date, time.min, tzinfo=learner_timezone)
        local_end = datetime.combine(
            local_date + timedelta(days=1),
            time.min,
            tzinfo=learner_timezone,
        )
        sent_today = await uow.instances.count_sent_for_learner_between(
            learner_id=instance.learner_id,
            starts_at=local_start.astimezone(timezone.utc),
            ends_at=local_end.astimezone(timezone.utc),
        )
        if sent_today >= max(0, effective_preferences.daily_cap):
            return "daily_cap_exceeded"
    return None
