import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database import crud
from database.engine import async_session
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk, split_chat_identifier
from utils.scheduling import (
    deserialize_days,
    humanize_days,
    parse_utc,
    compute_next_run_for_recurring,
    compute_next_run_for_one_time,
)


class ReminderScheduler:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._runner())

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _runner(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception as exc:
                logging.exception("Reminder scheduler failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        now_utc = datetime.now(timezone.utc)
        async with async_session() as session:
            due = await crud.fetch_due_reminders(session, now_utc)
            for reminder in due:
                reminder_id = reminder.id
                try:
                    await self._process_reminder(session, reminder, now_utc)
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    logging.exception(
                        "Failed to process reminder #%s: %s",
                        reminder_id,
                        exc,
                    )

    async def _process_reminder(self, session, reminder, now_utc: datetime) -> None:
        builder = InlineKeyboardBuilder()
        builder.button(text=texts.REMINDER_CONFIRM_BUTTON, callback_data=f"rem_confirm_{reminder.id}")
        builder.button(text=texts.REMINDER_DECLINE_BUTTON, callback_data=f"rem_decline_{reminder.id}")
        builder.adjust(1)

        contact_label, contact_target = split_chat_identifier(reminder.chat_identifier)
        send_target = contact_target or contact_label
        if not send_target:
            logging.error("Reminder #%s has no valid chat identifier", reminder.id)
            reminder.active = False
            await crud.save_lesson_reminder(session, reminder)
            return
        if isinstance(send_target, str) and send_target.lstrip('-').isdigit():
            send_target = int(send_target)

        schedule_text = self._build_schedule_text(reminder)
        message_text = texts.REMINDER_TRIGGER_MESSAGE.format(
            name=escape_html_text(reminder.student_name),
            schedule=escape_html_text(schedule_text),
        )

        contact_details = contact_label or contact_target or "—"
        if contact_target and contact_target != contact_details:
            contact_details = f"{contact_details} (id: {contact_target})"

        should_reschedule = True
        try:
            await self._bot.send_message(send_target, message_text, reply_markup=builder.as_markup())
        except TelegramBadRequest as exc:
            if "chat not found" in exc.message.lower():
                logging.warning(
                    "Chat not found for %s (rem #%s). Deactivating.",
                    contact_details,
                    reminder.id,
                )
                await self._handle_fatal_send_failure(
                    reminder,
                    contact_details,
                    "чат не найден",
                    "Чат не найден",
                    now_utc,
                )
                should_reschedule = False
            else:
                logging.error(
                    "Telegram API error for reminder #%s to %s: %s",
                    reminder.id,
                    contact_details,
                    exc,
                )
        except TelegramForbiddenError as exc:
            logging.warning(
                "Bot was blocked by %s (rem #%s): %s",
                contact_details,
                reminder.id,
                exc,
            )
            await self._handle_fatal_send_failure(
                reminder,
                contact_details,
                "бот заблокирован",
                "Бот заблокирован",
                now_utc,
            )
            should_reschedule = False
        except Exception as exc:
            logging.error(
                "Generic error for reminder #%s to %s: %s",
                reminder.id,
                contact_details,
                exc,
            )
        else:
            reminder.last_notified_at = now_utc
            await self._log_sent(reminder, schedule_text)

        if should_reschedule:
            await self._schedule_next(reminder, now_utc + timedelta(seconds=30))

        await crud.save_lesson_reminder(session, reminder)

    async def _schedule_next(self, reminder, reference: datetime) -> None:
        if reminder.is_recurring:
            if not reminder.lesson_time:
                reminder.next_run_at = None
                reminder.active = False
                return
            days = deserialize_days(reminder.days)
            next_run = compute_next_run_for_recurring(days, reminder.lesson_time, reminder.lead_minutes, reference)
            reminder.next_run_at = next_run
            reminder.active = next_run is not None
        else:
            lesson_dt = reminder.lesson_datetime
            if isinstance(lesson_dt, str):
                lesson_dt = parse_utc(lesson_dt)
            if lesson_dt and lesson_dt.tzinfo is None:
                lesson_dt = lesson_dt.replace(tzinfo=timezone.utc)
            next_run = compute_next_run_for_one_time(lesson_dt, reminder.lead_minutes, reference) if lesson_dt else None
            reminder.next_run_at = None
            reminder.active = False
            if next_run:
                # lesson still in future and not yet sent
                reminder.next_run_at = next_run
                reminder.active = True

    async def _log_sent(self, reminder, schedule: str) -> None:
        try:
            next_run = escape_html_text(format_timestamp_msk(reminder.next_run_at))
            log_text = texts.REMINDER_SENT_LOG.format(
                name=escape_html_text(reminder.student_name),
                schedule=escape_html_text(schedule),
                lead=escape_html_text(reminder.lead_minutes),
                next_run=next_run,
                mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
            )
            await self._bot.send_message(config.LOGS_CHAT_ID, log_text)
        except Exception as exc:
            logging.error(f"Failed to log reminder send: {exc}")

    def _build_schedule_text(self, reminder) -> str:
        if reminder.is_recurring:
            days = humanize_days(deserialize_days(reminder.days))
            return f"{days} в {reminder.lesson_time}" if reminder.lesson_time else days
        return format_timestamp_msk(reminder.lesson_datetime)

    async def _handle_fatal_send_failure(
        self,
        reminder,
        contact_details: str,
        comment_reason: str,
        admin_reason: str,
        now_utc: datetime,
    ) -> None:
        reminder.active = False
        reminder.next_run_at = None
        deactivation_date = now_utc.strftime('%Y-%m-%d')
        system_note = f"[СИСТЕМА] Отключено {deactivation_date} ({comment_reason})."
        comment = reminder.comment or ""
        if system_note not in comment:
            comment = f"{comment}\n{system_note}" if comment else system_note
        reminder.comment = comment

        admin_message = (
            "⚠️ <b>Напоминание отключено</b>\n\n"
            f"Не удалось отправить напоминание #{escape_html_text(reminder.id, default='—')} для "
            f"<b>{escape_html_text(reminder.student_name)}</b> (контакт: <code>{escape_html_text(contact_details)}</code>).\n"
            f"Причина: <code>{escape_html_text(admin_reason)}</code>\n\n"
            "Напоминание было автоматически деактивировано. Пожалуйста, проверьте и обновите контактные данные студента."
        )
        try:
            for admin_id in config.ADMINS:
                await self._bot.send_message(admin_id, admin_message)
        except Exception as admin_exc:
            logging.error(
                "Failed to notify admin about failed reminder #%s: %s",
                reminder.id,
                admin_exc,
            )
