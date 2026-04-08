from dataclasses import dataclass

import pytest

from notifications.application.dto import NotificationResponseDraft, NotificationResponseRecord
from notifications.application.responses import RecordNotificationResponseUseCase
from notifications.domain.enums import EventType


@dataclass
class FakeResponseRepository:
    records: list[NotificationResponseDraft]

    async def record_response(self, draft):
        self.records.append(draft)
        return NotificationResponseRecord(
            response_id=301,
            notification_instance_id=draft.notification_instance_id,
            event_type=EventType.LESSON,
            event_id=617,
            learner_id=10,
            response_value=draft.response_value,
            lesson_participant_state_updated=True,
        )


@dataclass
class FakeUnitOfWork:
    responses: FakeResponseRepository
    committed: bool = False

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_record_notification_response_persists_response_and_commits():
    response_repo = FakeResponseRepository(records=[])
    uow = FakeUnitOfWork(responses=response_repo)
    draft = NotificationResponseDraft(
        notification_instance_id=101,
        action_key="confirm_lesson",
        response_value="confirmed",
    )

    result = await RecordNotificationResponseUseCase(uow).execute(draft)

    assert uow.committed
    assert response_repo.records == [draft]
    assert result.response_id == 301
    assert result.lesson_participant_state_updated is True
