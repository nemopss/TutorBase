from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from config import config

logger = logging.getLogger(__name__)


class EmailDeliveryNotConfiguredError(RuntimeError):
    """Raised when SMTP delivery settings are incomplete."""


def _smtp_is_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USERNAME and config.SMTP_PASSWORD)


def _send_message_sync(message: EmailMessage) -> None:
    if not _smtp_is_configured():
        raise EmailDeliveryNotConfiguredError("SMTP delivery is not configured")

    if config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=config.SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
        return

    with smtplib.SMTP(
        config.SMTP_HOST,
        config.SMTP_PORT,
        timeout=config.SMTP_TIMEOUT_SECONDS,
    ) as smtp:
        smtp.starttls()
        smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        smtp.send_message(message)


async def send_email_verification(*, to_email: str, display_name: str, verify_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Подтвердите email в TutorBase"
    message["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM_EMAIL))
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                f"Здравствуйте, {display_name}.",
                "",
                "Подтвердите email для входа в TutorBase:",
                verify_url,
                "",
                "Если вы не регистрировались в TutorBase, просто проигнорируйте это письмо.",
            ]
        )
    )

    try:
        await asyncio.to_thread(_send_message_sync, message)
    except EmailDeliveryNotConfiguredError:
        raise
    except Exception:
        logger.exception("Email verification delivery failed")
        raise
