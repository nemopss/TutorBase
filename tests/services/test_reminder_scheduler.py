import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from aiogram.exceptions import TelegramBadRequest

from services.reminders import ReminderScheduler
from services.reminder_definitions import REMINDER_TYPE_LESSON_CONFIRM
from services import billing_service
from database import crud
from config import config


class DummyBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text))


class DummySession:
    def add(self, instance):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


@pytest.fixture
def scheduler(monkeypatch):
    bot = DummyBot()
    sched = ReminderScheduler(bot)
    monkeypatch.setattr(config, "ADMINS", [999])

    async def fake_should_suppress(session, instance):
        return False

    async def fake_notifications_allowed(session, tenant_id):
        return True

    monkeypatch.setattr(sched, "_should_suppress_legacy_instance", fake_should_suppress)
    monkeypatch.setattr(
        billing_service,
        "notifications_allowed_for_tenant",
        fake_notifications_allowed,
    )
    return sched


def _make_instance(**overrides):
    learner = overrides.pop(
        "learner",
        SimpleNamespace(
            notifications_enabled=True,
            id=1,
            display_name="Learner",
            bot_user=SimpleNamespace(chat_id=123),
        ),
    )
    defaults = dict(
        id=1,
        tenant_id=1,
        learner_id=learner.id,
        learner=learner,
        package=overrides.pop("package", SimpleNamespace(learner=learner)),
        package_id=1,
        lesson=SimpleNamespace(id=2, scheduled_at=datetime.now(timezone.utc), sequence_index=1),
        rule=SimpleNamespace(reminder_type=REMINDER_TYPE_LESSON_CONFIRM),
        payload={"student_name": "Learner"},
        chat_identifier="chat:123",
        scheduled_for=datetime.now(timezone.utc),
        status="scheduled",
        active=True,
        comment=None,
        last_notified_at=None,
        last_response=None,
        last_response_at=None,
        last_decline_reason=None,
        retry_count=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_process_instance_notifications_disabled(scheduler, monkeypatch):
    calls = []

    async def fake_set_status(session, instance, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)
    instance = _make_instance(learner=SimpleNamespace(notifications_enabled=False, id=1, display_name="Learner"))

    await scheduler._process_instance(DummySession(), instance, datetime.now(timezone.utc))

    assert calls[0]["status"] == "skipped"
    assert calls[0]["active"] is False


@pytest.mark.asyncio
async def test_process_instance_suppresses_legacy_when_new_notifications_enabled(
    scheduler,
    monkeypatch,
):
    calls = []

    async def fake_set_status(session, instance, **kwargs):
        calls.append(kwargs)

    async def fake_should_suppress(session, instance):
        return True

    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)
    monkeypatch.setattr(scheduler, "_should_suppress_legacy_instance", fake_should_suppress)

    await scheduler._process_instance(DummySession(), _make_instance(), datetime.now(timezone.utc))

    assert calls[0]["status"] == "skipped"
    assert calls[0]["active"] is False
    assert calls[0]["comment"] == "Suppressed by new notification system"
    assert scheduler._bot.sent == []


@pytest.mark.asyncio
async def test_process_instance_missing_chat_identifier(scheduler, monkeypatch):
    calls = []

    async def fake_set_status(session, instance, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)
    learner = SimpleNamespace(notifications_enabled=True, id=1, display_name="Learner", bot_user=None)
    instance = _make_instance(chat_identifier=None, learner=learner, package=SimpleNamespace(learner=learner))

    await scheduler._process_instance(DummySession(), instance, datetime.now(timezone.utc))
    assert calls[0]["status"] == "failed"
    assert calls[0]["comment"] == "Missing chat identifier"


@pytest.mark.asyncio
async def test_process_instance_send_success(scheduler, monkeypatch):
    statuses = []

    async def fake_set_status(session, instance, **kwargs):
        statuses.append(kwargs)

    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)
    instance = _make_instance()

    await scheduler._process_instance(DummySession(), instance, datetime.now(timezone.utc))
    assert statuses[-1]["status"] == "sent"


@pytest.mark.asyncio
async def test_process_instance_permanent_failure(scheduler, monkeypatch):
    statuses = []
    admin_notifications = []

    async def fake_send_message(chat_id, text, reply_markup=None):
        if chat_id == "chat:123":
            raise TelegramBadRequest(method="sendMessage", message="invalid")
        admin_notifications.append(chat_id)

    async def fake_set_status(session, instance, **kwargs):
        statuses.append(kwargs)

    scheduler._bot.send_message = fake_send_message
    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)

    instance = _make_instance()
    await scheduler._process_instance(DummySession(), instance, datetime.now(timezone.utc))

    assert statuses[0]["status"] == "failed"
    assert config.ADMINS[0] in admin_notifications


@pytest.mark.asyncio
async def test_process_instance_temporary_failure(scheduler, monkeypatch):
    statuses = []

    async def fake_send_message(chat_id, text, reply_markup=None):
        raise RuntimeError("timeout")

    async def fake_set_status(session, instance, **kwargs):
        statuses.append(kwargs)

    scheduler._bot.send_message = fake_send_message
    monkeypatch.setattr(crud, "set_reminder_instance_status", fake_set_status)

    instance = _make_instance()
    await scheduler._process_instance(DummySession(), instance, datetime.now(timezone.utc))
    assert statuses[0]["status"] == "pending"
    assert statuses[0]["active"] is True
