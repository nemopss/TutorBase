from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from notifications.application.dto import NotificationAuditLogDraft
from notifications.application.dto import NotificationAuditLogRecord
from notifications.application.ports import NotificationMaterializationUnitOfWork


class ListNotificationAuditLogUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        limit: int = 100,
    ) -> tuple[NotificationAuditLogRecord, ...]:
        return await self._uow.audit_log.list_audit(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )


async def record_notification_audit(
    uow: NotificationMaterializationUnitOfWork,
    *,
    entity_type: str,
    entity_id: int | None,
    action: str,
    actor_user_id: int | None = None,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await uow.audit_log.record_audit(
        NotificationAuditLogDraft(
            actor_type="teacher" if actor_user_id is not None else "system",
            actor_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=_snapshot(before),
            after=_snapshot(after),
            reason=reason,
            metadata=_snapshot(metadata or {}),
        )
    )


def _snapshot(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return _snapshot(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _snapshot(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set):
        return [_snapshot(item) for item in value]
    return value
