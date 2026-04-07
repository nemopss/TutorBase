from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from notifications.application.delivery import NotificationDeliveryError
from notifications.application.dto import ClaimedNotificationInstance, RenderedNotification
from notifications.domain.enums import CategoryKey, EventType, Priority
from notifications.infrastructure.telegram_delivery import TelegramNotificationChannelAdapter


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, *, reply_markup=None, parse_mode=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )
        return SimpleNamespace(message_id=777)


def _claimed_instance(*, provider_chat_id: str | None = "5390064156") -> ClaimedNotificationInstance:
    return ClaimedNotificationInstance(
        instance_id=101,
        attempt_id=201,
        attempt_no=1,
        rule_id=1,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        priority=Priority.NORMAL,
        channel="telegram",
        provider_chat_id=provider_chat_id,
    )


@pytest.mark.asyncio
async def test_telegram_adapter_sends_message_and_returns_provider_metadata():
    bot = FakeBot()

    result = await TelegramNotificationChannelAdapter(bot).send(
        instance=_claimed_instance(),
        rendered=RenderedNotification(text="Привет, Вика!", parse_mode=None),
    )

    assert bot.calls == [
        {
            "chat_id": "5390064156",
            "text": "Привет, Вика!",
            "reply_markup": None,
            "parse_mode": None,
        }
    ]
    assert result.provider == "telegram"
    assert result.provider_chat_id == "5390064156"
    assert result.provider_message_id == "777"


@pytest.mark.asyncio
async def test_telegram_adapter_converts_reply_markup_snapshot():
    bot = FakeBot()

    await TelegramNotificationChannelAdapter(bot).send(
        instance=_claimed_instance(),
        rendered=RenderedNotification(
            text="Привет, Вика!",
            reply_markup_snapshot={
                "inline_keyboard": [
                    [{"text": "✅ Всё в силе", "callback_data": "notif_confirm_lesson_101"}]
                ]
            },
        ),
    )

    reply_markup = bot.calls[0]["reply_markup"]
    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].callback_data == "notif_confirm_lesson_101"


@pytest.mark.asyncio
async def test_telegram_adapter_fails_permanently_without_chat_id():
    with pytest.raises(NotificationDeliveryError) as exc_info:
        await TelegramNotificationChannelAdapter(FakeBot()).send(
            instance=_claimed_instance(provider_chat_id=None),
            rendered=RenderedNotification(text="Привет, Вика!"),
        )

    assert exc_info.value.error_code == "telegram_no_contact"
    assert exc_info.value.retryable is False
