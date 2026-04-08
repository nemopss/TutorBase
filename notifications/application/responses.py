from __future__ import annotations

from notifications.application.dto import NotificationResponseDraft, NotificationResponseRecord
from notifications.application.ports import NotificationMaterializationUnitOfWork


class RecordNotificationResponseUseCase:
    def __init__(self, uow: NotificationMaterializationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, draft: NotificationResponseDraft) -> NotificationResponseRecord:
        record = await self._uow.responses.record_response(draft)
        await self._uow.commit()
        return record
