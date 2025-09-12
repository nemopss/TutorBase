from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import config

class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        # Этот метод будет автоматически вызываться aiogram
        # и возвращать True, если ID пользователя есть в списке админов,
        # и False, если нет.
        return event.from_user.id in config.ADMINS
