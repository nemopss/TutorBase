from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from config import config


async def set_bot_commands(bot: Bot):
    """
    Устанавливает команды для разных ролей (пользователи и админы).
    """
    # Команды для обычных пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Запуск/перезапуск бота")
    ]
    await bot.set_my_commands(user_commands, BotCommandScopeDefault())

    # Команды для администраторов
    admin_commands = [
        BotCommand(command="start", description="🚀 Запуск/перезапуск бота"),
        BotCommand(command="admin", description="👑 Панель администратора"),
        BotCommand(command="status", description="📊 Текущий статус бота"),
    ]

    # Устанавливаем персональные команды для каждого админа из конфига
    for admin_id in config.ADMINS:
        await bot.set_my_commands(admin_commands, BotCommandScopeChat(chat_id=admin_id))
