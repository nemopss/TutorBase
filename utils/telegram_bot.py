from __future__ import annotations

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from config import config


def build_telegram_bot(*, parse_mode: str | None = None) -> Bot:
    session = AiohttpSession(timeout=config.TELEGRAM_REQUEST_TIMEOUT_SECONDS)
    return Bot(token=config.BOT_TOKEN, session=session, parse_mode=parse_mode)
