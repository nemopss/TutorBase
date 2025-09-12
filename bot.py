import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from utils.commands import set_bot_commands
from config import config
from database.db import init_db
from handlers import admin as admin_h
from handlers import application as app_h
from handlers import start as start_h


async def main():
    await init_db()

    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    # storage = MemoryStorage()
    storage = RedisStorage.from_url(config.REDIS_URL)
    dp = Dispatcher(storage=storage)

    await set_bot_commands(bot)

    dp.include_router(start_h.router)
    dp.include_router(app_h.router)
    dp.include_router(admin_h.router)

    logging.info("Bot started...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
    except ValueError as e:
        logging.error(e)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
