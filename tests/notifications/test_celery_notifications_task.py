import importlib
import sys

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


def test_celery_app_import_registers_notification_tasks():
    for module_name in (
        "utils.tasks",
        "utils.tasks.reminders",
        "utils.tasks.metrics",
        "utils.tasks.notifications",
        "utils.celery_app",
    ):
        sys.modules.pop(module_name, None)

    reloaded_celery_app = importlib.import_module("utils.celery_app").celery_app

    assert "utils.tasks.notifications.process_notification_jobs" in reloaded_celery_app.tasks
    assert "utils.tasks.notifications.deliver_due_notifications" in reloaded_celery_app.tasks


@pytest.mark.asyncio
async def test_active_tenant_ids_returns_ordered_ids_from_query_result():
    session = FakeSession([1, 2])

    result = await _active_tenant_ids(session)

    assert result == (1, 2)
    assert session.statements
