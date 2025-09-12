import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from utils.commands import set_bot_commands
from config import config
from database.db import init_db
from handlers import admin as admin_h
from handlers import application as app_h
from handlers import start as start_h
from handlers import funnel as funnel_h
from handlers import cases as cases_h
from middlewares.logging import LoggingMiddleware, LoggingFilter


async def main():
    await init_db()

    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    # storage = MemoryStorage()
    storage = RedisStorage.from_url(config.REDIS_URL)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(LoggingMiddleware())

    await set_bot_commands(bot)

    dp.include_router(start_h.router)
    dp.include_router(app_h.router)
    dp.include_router(admin_h.router)
    dp.include_router(funnel_h.router)
    dp.include_router(cases_h.router)

    logging.info("Bot started...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    formatter = logging.Formatter("[%(asctime)s] [%(update_id)s] %(levelname)s - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(LoggingFilter())

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
    except ValueError as e:
        logging.error(e)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
