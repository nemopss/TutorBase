from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from notifications.application.delivery import NotificationDeliveryError
from notifications.application.dto import (
    ClaimedNotificationInstance,
    DeliverySendResult,
    RenderedNotification,
)


class TelegramNotificationChannelAdapter:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(
        self,
        *,
        instance: ClaimedNotificationInstance,
        rendered: RenderedNotification,
    ) -> DeliverySendResult:
        if not instance.provider_chat_id:
            raise NotificationDeliveryError(
                "Recipient has no Telegram chat id",
                error_code="telegram_no_contact",
                retryable=False,
            )

        try:
            message = await self._bot.send_message(
                instance.provider_chat_id,
                rendered.text,
                reply_markup=_reply_markup(rendered.reply_markup_snapshot),
                parse_mode=rendered.parse_mode,
            )
        except TelegramBadRequest as exc:
            raise NotificationDeliveryError(
                str(exc),
                error_code="telegram_bad_request",
                retryable=False,
            ) from exc
        except TelegramForbiddenError as exc:
            raise NotificationDeliveryError(
                str(exc),
                error_code="telegram_forbidden",
                retryable=False,
            ) from exc
        except Exception as exc:
            raise NotificationDeliveryError(
                str(exc),
                error_code="telegram_transient_error",
                retryable=True,
            ) from exc

        return DeliverySendResult(
            provider="telegram",
            provider_chat_id=str(instance.provider_chat_id),
            provider_message_id=str(message.message_id),
            sent_at=datetime.now(timezone.utc),
        )


def _reply_markup(snapshot: dict | None) -> InlineKeyboardMarkup | None:
    if not snapshot:
        return None
    return InlineKeyboardMarkup(**snapshot)
