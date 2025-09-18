import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        from_user = data.get("event_from_user")

        if from_user is None and isinstance(event, Update):
            try:
                payload = event.event
            except Exception:
                payload = None

            if payload is not None:
                from_user = getattr(payload, "from_user", None)
                if from_user is None:
                    from_user = getattr(payload, "user", None)

        if session and from_user:
            # The commit is handled by the DbSessionMiddleware
            await crud.upsert_bot_user(session, from_user)

        return await handler(event, data)
