import logging
from typing import Callable, Dict, Any, Awaitable
from contextvars import ContextVar

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

update_id_var = ContextVar('update_id', default='unknown')

class LoggingFilter(logging.Filter):
    def filter(self, record):
        record.update_id = update_id_var.get()
        return True

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        update_id_var.set(event.update_id)
        return await handler(event, data)
