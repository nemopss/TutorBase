from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from notifications.application.reconciliation import QueueNotificationEventReconciliationUseCase
from notifications.domain.enums import EventType, NotificationSystemMode
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork


async def enqueue_notification_event_reconciliation(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    event_type: EventType,
    event_id: int,
    reason: str,
    delivery_enabled: bool | None = None,
    shadow: bool | None = None,
) -> None:
    if current_tenant.tenant_id is None:
        return

    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=current_tenant.tenant_id)
    settings = await uow.settings.get_settings()
    effective_delivery_enabled = (
        settings.mode == NotificationSystemMode.NEW if delivery_enabled is None else delivery_enabled
    )
    effective_shadow = settings.mode != NotificationSystemMode.NEW if shadow is None else shadow
    await QueueNotificationEventReconciliationUseCase(uow).execute(
        event_type=event_type,
        event_id=event_id,
        reason=reason,
        delivery_enabled=effective_delivery_enabled,
        shadow=effective_shadow,
        commit=False,
    )
