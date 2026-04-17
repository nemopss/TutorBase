import importlib
import sys
from datetime import datetime, timezone

import pytest

from utils.tasks.notifications import (
    _active_tenant_ids,
    _build_delivery_log_message,
    NotificationDeliveryLogContext,
    deliver_due_notifications_task,
    process_notification_jobs_task,
)
from utils.celery_app import _build_notifications_beat_schedule
from utils.telegram_bot import build_telegram_bot
from config import config


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


def test_notifications_beat_schedule_is_empty_when_automation_is_disabled():
    schedule = _build_notifications_beat_schedule(
        notifications_automation_enabled=False,
        process_jobs_interval_seconds=60,
        delivery_interval_seconds=30,
    )

    assert schedule == {}


def test_notifications_beat_schedule_registers_process_and_delivery_tasks():
    schedule = _build_notifications_beat_schedule(
        notifications_automation_enabled=True,
        process_jobs_interval_seconds=60,
        delivery_interval_seconds=30,
    )

    assert set(schedule) == {"notifications.process-jobs", "notifications.deliver-due"}
    assert schedule["notifications.process-jobs"]["task"] == "utils.tasks.notifications.process_notification_jobs"
    assert schedule["notifications.process-jobs"]["schedule"] == 60
    assert schedule["notifications.process-jobs"]["options"]["expires"] == 55
    assert schedule["notifications.deliver-due"]["task"] == "utils.tasks.notifications.deliver_due_notifications"
    assert schedule["notifications.deliver-due"]["schedule"] == 30
    assert schedule["notifications.deliver-due"]["options"]["expires"] == 25


@pytest.mark.asyncio
async def test_build_telegram_bot_uses_configured_request_timeout():
    bot = build_telegram_bot()

    try:
        assert bot.session.timeout == config.TELEGRAM_REQUEST_TIMEOUT_SECONDS
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_active_tenant_ids_returns_ordered_ids_from_query_result():
    session = FakeSession([1, 2])

    result = await _active_tenant_ids(session)

    assert result == (1, 2)
    assert session.statements


def test_build_delivery_log_message_is_human_readable():
    context = NotificationDeliveryLogContext(
        learner_name="Testlex",
        category_name="Подтверждение урока",
        event_type="lesson",
        lesson_scheduled_at=datetime(2026, 4, 9, 19, 0, tzinfo=timezone.utc),
    )

    message = _build_delivery_log_message(
        context,
        provider_message_id="3106",
    )

    assert "#notification_sent" in message
    assert "Testlex" in message
    assert "Подтверждение урока" in message
    assert "2026-04-09 22:00:00 MSK" in message
    assert "3106" in message
