from datetime import datetime, timezone

import pytest

from config import config
from handlers.notifications import (
    NotificationResponseContext,
    _build_response_log_message,
    _build_teacher_response_message,
    _notify_about_response,
    _parse_instance_id,
    _tenant_id_for_instance,
)


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, value):
        self.value = value
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.value)


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
        )


def test_parse_instance_id_accepts_known_notification_prefix():
    assert _parse_instance_id("notif_confirm_lesson_101", prefix="notif_confirm_lesson_") == 101
    assert _parse_instance_id("bad_101", prefix="notif_confirm_lesson_") is None
    assert _parse_instance_id("notif_confirm_lesson_bad", prefix="notif_confirm_lesson_") is None


@pytest.mark.asyncio
async def test_tenant_id_for_instance_reads_tenant_from_notification_instance():
    session = FakeSession(1)

    tenant_id = await _tenant_id_for_instance(session, 101)

    assert tenant_id == 1
    assert session.statements


def test_build_teacher_response_message_for_confirmed_lesson():
    context = NotificationResponseContext(
        tenant_id=1,
        learner_name="Testlex",
        event_type="lesson",
        lesson_scheduled_at=datetime(2026, 4, 9, 19, 0, tzinfo=timezone.utc),
    )

    message = _build_teacher_response_message(
        context,
        response_value="confirmed",
    )

    assert "Testlex" in message
    assert "подтвердил урок" in message
    assert "2026-04-09 22:00:00 MSK" in message


def test_build_teacher_response_message_for_confirmed_package_renewal():
    context = NotificationResponseContext(
        tenant_id=1,
        learner_name="Testlex",
        event_type="package",
        package_title="Пакет апрель",
        package_end_at=datetime(2026, 4, 30, 21, 0, tzinfo=timezone.utc),
    )

    message = _build_teacher_response_message(
        context,
        response_value="confirmed",
    )

    assert "Testlex" in message
    assert "подтвердил продолжение занятий" in message
    assert "Пакет апрель" in message
    assert "2026-05-01 00:00:00 MSK" in message


def test_build_response_log_message_for_declined_lesson_includes_reason():
    context = NotificationResponseContext(
        tenant_id=1,
        learner_name="Testlex",
        event_type="lesson",
        lesson_scheduled_at=datetime(2026, 4, 9, 19, 0, tzinfo=timezone.utc),
    )

    message = _build_response_log_message(
        context,
        response_value="declined",
        response_text="Не успеваю",
    )

    assert "#notification_decline" in message
    assert "Testlex" in message
    assert "Не успеваю" in message


def test_build_response_log_message_for_declined_package_renewal():
    context = NotificationResponseContext(
        tenant_id=1,
        learner_name="Testlex",
        event_type="package",
        package_title="Пакет апрель",
        package_end_at=datetime(2026, 4, 30, 21, 0, tzinfo=timezone.utc),
    )

    message = _build_response_log_message(
        context,
        response_value="needs_discussion",
    )

    assert "#notification_package_renewal_discuss" in message
    assert "Testlex" in message
    assert "хочет обсудить продление пакета" in message
    assert "Пакет апрель" in message


@pytest.mark.asyncio
async def test_notify_about_response_sends_log_and_teacher_messages(monkeypatch):
    async def fake_context(_session, _instance_id):
        return NotificationResponseContext(
            tenant_id=1,
            learner_name="Testlex",
            event_type="lesson",
            lesson_scheduled_at=datetime(2026, 4, 9, 19, 0, tzinfo=timezone.utc),
        )

    async def fake_recipients(_session, _tenant_id):
        return (111111, 222222)

    monkeypatch.setattr("handlers.notifications._notification_response_context", fake_context)
    monkeypatch.setattr("handlers.notifications._teacher_recipient_ids_for_tenant", fake_recipients)

    bot = FakeBot()

    await _notify_about_response(
        bot,
        FakeSession(None),
        instance_id=101,
        response_value="confirmed",
    )

    assert [item["chat_id"] for item in bot.messages] == [config.LOGS_CHAT_ID, 111111, 222222]
    assert all(item["parse_mode"] == "HTML" for item in bot.messages)
    assert any("подтвердил урок" in item["text"] for item in bot.messages)
