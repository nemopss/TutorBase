import asyncio
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from utils.commands import set_bot_commands
from utils.formatters import escape_html_text, format_timestamp_msk
from utils.state import set_bot_started_at
from config import config
from handlers import admin as admin_h
from handlers import admin_packages as admin_packages_h
from handlers import admin_test_reminders as admin_test_reminders_h
from handlers import application as app_h
from handlers import start as start_h
from handlers import funnel as funnel_h
from handlers import cases as cases_h
from handlers import reminders as reminders_h
from middlewares.logging import LoggingMiddleware, LoggingFilter
from middlewares.db import DbSessionMiddleware
from middlewares.user_tracking import UserTrackingMiddleware
from middlewares.rate_limit import RateLimitMiddleware
from services.reminders import ReminderScheduler
from utils import texts


async def main():
    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    started_at = datetime.now(timezone.utc)
    set_bot_started_at(started_at)
    # storage = MemoryStorage()
    storage = RedisStorage.from_url(config.REDIS_URL)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserTrackingMiddleware())
    dp.update.middleware(RateLimitMiddleware(max_requests=20, window_seconds=60))
    dp.update.middleware(LoggingMiddleware())

    reminder_scheduler = ReminderScheduler(bot)
    dp.startup.register(reminder_scheduler.start)
    dp.shutdown.register(reminder_scheduler.stop)

    try:
        await set_bot_commands(bot)
    except Exception as e:
        logging.error(f"Failed to set bot commands: {e}")

    dp.include_router(start_h.router)
    dp.include_router(app_h.router)
    dp.include_router(admin_h.router)
    dp.include_router(admin_packages_h.router)
    dp.include_router(admin_test_reminders_h.router)
    dp.include_router(funnel_h.router)
    dp.include_router(cases_h.router)
    dp.include_router(reminders_h.router)

    try:
        startup_time = escape_html_text(format_timestamp_msk(started_at))
        startup_message = texts.STARTUP_DEPLOY_NOTIFICATION.format(time=startup_time)
        await bot.send_message(config.LOGS_CHAT_ID, startup_message)
    except Exception as exc:
        logging.error("Failed to notify about deployment: %s", exc)

    logging.info("Bot started...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
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
        logging.error(f"Configuration error: ({e})", exc_info=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred: ({e})", exc_info=True)
