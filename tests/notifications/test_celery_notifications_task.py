import pytest

from utils.tasks.notifications import (
    _active_tenant_ids,
    deliver_due_notifications_task,
    process_notification_jobs_task,
)


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class FakeSession:
    def __init__(self, values):
        self.values = values
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.values)


def test_deliver_due_notifications_task_is_registered_with_expected_name():
    assert deliver_due_notifications_task.name == "utils.tasks.notifications.deliver_due_notifications"


def test_process_notification_jobs_task_is_registered_with_expected_name():
    assert process_notification_jobs_task.name == "utils.tasks.notifications.process_notification_jobs"


@pytest.mark.asyncio
async def test_active_tenant_ids_returns_ordered_ids_from_query_result():
    session = FakeSession([1, 2])

    result = await _active_tenant_ids(session)

    assert result == (1, 2)
    assert session.statements
