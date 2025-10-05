import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from config import config
from database import crud
from database.engine import async_session
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk, split_chat_identifier
from utils.scheduling import parse_utc
from zoneinfo import ZoneInfo

from services.reminder_definitions import (
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_PAYMENT_WEEK,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
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
            await self._process_instances(session, now_utc)

    async def _process_instances(self, session, now_utc: datetime) -> None:
        instances = await crud.fetch_reminder_instances_due(session, now_utc)
        for instance in instances:
            instance_id = instance.id
            try:
                await self._process_instance(session, instance, now_utc)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logging.exception(
                    "Failed to process reminder instance #%s: %s",
                    instance_id,
                    exc,
                )

    async def _process_instance(self, session, instance, now_utc: datetime) -> None:
        target, contact_display = self._resolve_instance_target(instance)
        if not target:
            logging.error(
                "Reminder instance #%s has no valid chat identifier (package %s)",
                instance.id,
                instance.package_id,
            )
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='failed',
                active=False,
                comment='Missing chat identifier',
            )
            return

        schedule_label = self._build_instance_schedule(instance)
        message_text, keyboard = self._build_instance_message(instance, schedule_label)
        if not message_text:
            logging.error(
                "Reminder instance #%s has no message text (type=%s)",
                instance.id,
                getattr(instance.rule, 'reminder_type', 'unknown'),
            )
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='failed',
                active=False,
                comment='Empty message text',
            )
            return

        try:
            await self._bot.send_message(target, message_text, reply_markup=keyboard)
        except TelegramBadRequest as exc:
            await self._handle_instance_send_failure(session, instance, contact_display, 'TelegramBadRequest', exc, now_utc)
        except TelegramForbiddenError as exc:
            await self._handle_instance_send_failure(session, instance, contact_display, 'TelegramForbiddenError', exc, now_utc)
        except Exception as exc:
            await self._handle_instance_send_failure(session, instance, contact_display, 'GenericError', exc, now_utc)
        else:
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='sent',
                active=False,
                last_notified_at=now_utc,
            )
            await self._log_instance_sent(instance, schedule_label)

    async def _handle_instance_send_failure(self, session, instance, contact_display: str, reason: str, exc: Exception, now_utc: datetime) -> None:
        logging.error(
            "Failed to send reminder instance #%s to %s: %s (%s)",
            instance.id,
            contact_display,
            exc,
            reason,
        )
        comment = f"Send failure ({reason}): {exc}"[:1000]
        await crud.set_reminder_instance_status(
            session,
            instance,
            status='failed',
            active=False,
            comment=comment,
        )
        admin_message = (
            "⚠️ <b>Не удалось отправить напоминание</b>\n\n"
            f"Инстанс #{escape_html_text(instance.id)} ({escape_html_text(self._describe_instance_kind(instance))})\n"
            f"Ученик: {escape_html_text(self._instance_student_name(instance))}\n"
            f"Контакт: <code>{escape_html_text(contact_display or '—')}</code>\n"
            f"Причина: <code>{escape_html_text(str(exc))}</code>"
        )
        for admin_id in config.ADMINS:
            try:
                await self._bot.send_message(admin_id, admin_message)
            except Exception as send_exc:
                logging.error(
                    "Failed to notify admin about instance #%s failure: %s",
                    instance.id,
                    send_exc,
                )


    def _describe_instance_kind(self, instance) -> str:
        reminder_type = getattr(instance.rule, 'reminder_type', '') if instance.rule else ''
        if reminder_type == REMINDER_TYPE_LESSON_CONFIRM:
            return texts.REMINDER_TYPE_RECURRING
        if reminder_type == REMINDER_TYPE_LESSON_DAY_BEFORE:
            return texts.REMINDER_TYPE_LESSON_DAY_BEFORE
        if reminder_type == REMINDER_TYPE_PAYMENT_WEEK:
            return texts.REMINDER_TYPE_PAYMENT_WEEK
        if reminder_type == REMINDER_TYPE_PAYMENT_DAY:
            return texts.REMINDER_TYPE_PAYMENT_DAY
        if reminder_type == REMINDER_TYPE_HOMEWORK:
            return texts.REMINDER_TYPE_HOMEWORK
        if reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL:
            return texts.REMINDER_TYPE_PACKAGE_RENEWAL
        return reminder_type or "—"

    def _instance_student_name(self, instance) -> str:
        payload = instance.payload or {}
        return payload.get('student_name') or (instance.learner.display_name if instance.learner else '—')

    def _resolve_instance_target(self, instance) -> Tuple[Optional[int | str], str]:
        identifier = instance.chat_identifier
        if not identifier and instance.learner and instance.learner.bot_user:
            chat_id = instance.learner.bot_user.chat_id
            identifier = str(chat_id)
        label, actual = split_chat_identifier(identifier)
        target: Optional[int | str] = actual or label or None
        if isinstance(target, str) and target.lstrip('-').isdigit():
            target = int(target)
        contact_display = label or actual or ''
        return target, contact_display

    def _build_instance_schedule(self, instance) -> str:
        lesson = instance.lesson
        tz_name = getattr(instance.package, 'timezone', 'Europe/Moscow') if instance.package else 'Europe/Moscow'
        if lesson and lesson.scheduled_at:
            return self._format_with_timezone(lesson.scheduled_at, tz_name)
        payload = instance.payload or {}
        if 'schedule_label' in payload:
            return payload['schedule_label']
        if instance.scheduled_for:
            return self._format_with_timezone(instance.scheduled_for, tz_name)
        return '—'

    def _format_with_timezone(self, dt: datetime, tz_name: str) -> str:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo('Europe/Moscow')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        localized = dt.astimezone(tz)
        return localized.strftime('%Y-%m-%d %H:%M %Z')

    def _build_instance_message(self, instance, schedule_label: str) -> Tuple[Optional[str], Optional[InlineKeyboardMarkup]]:
        reminder_type = getattr(instance.rule, 'reminder_type', '') if instance.rule else ''
        name = escape_html_text(self._instance_student_name(instance))
        payload = instance.payload or {}

        if reminder_type == REMINDER_TYPE_LESSON_CONFIRM:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text=texts.REMINDER_CONFIRM_BUTTON, callback_data=f"remi_confirm_{instance.id}")
            keyboard.button(text=texts.REMINDER_DECLINE_BUTTON, callback_data=f"remi_decline_{instance.id}")
            keyboard.adjust(1)
            message = texts.REMINDER_TRIGGER_MESSAGE.format(
                name=name,
                schedule=escape_html_text(schedule_label),
            )
            return message, keyboard.as_markup()

        if reminder_type == REMINDER_TYPE_LESSON_DAY_BEFORE:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text=texts.REMINDER_CONFIRM_BUTTON, callback_data=f"remi_confirm_{instance.id}")
            keyboard.button(text=texts.REMINDER_DECLINE_BUTTON, callback_data=f"remi_decline_{instance.id}")
            keyboard.adjust(1)
            message = texts.REMINDER_DAY_BEFORE_MESSAGE.format(
                name=name,
                schedule=escape_html_text(schedule_label),
            )
            return message, keyboard.as_markup()

        if reminder_type == REMINDER_TYPE_PAYMENT_WEEK:
            return texts.PAYMENT_REMINDER_WEEK_BEFORE, None

        if reminder_type == REMINDER_TYPE_PAYMENT_DAY:
            return texts.PAYMENT_REMINDER_DAY_BEFORE, None

        if reminder_type == REMINDER_TYPE_HOMEWORK:
            return (
                texts.HOMEWORK_REMINDER_MESSAGE.format(
                    name=name,
                    schedule=escape_html_text(schedule_label),
                ),
                None,
            )

        if reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL:
            end_label = payload.get('package_end') or schedule_label
            return (
                texts.PACKAGE_RENEWAL_REMINDER_MESSAGE.format(
                    name=name,
                    end_date=escape_html_text(end_label),
                ),
                None,
            )

        # Fallback to generic behaviour
        return (
            texts.REMINDER_TRIGGER_MESSAGE.format(
                name=name,
                schedule=escape_html_text(schedule_label),
            ),
            None,
        )

    async def _log_instance_sent(self, instance, schedule: str) -> None:
        try:
            log_text = texts.REMINDER_SENT_LOG.format(
                name=escape_html_text(self._instance_student_name(instance)),
                schedule=escape_html_text(schedule),
                lead=escape_html_text(instance.payload.get('lead_minutes', '—') if instance.payload else '—'),
                next_run=escape_html_text('-'),
                kind=escape_html_text(self._describe_instance_kind(instance)),
                mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
            )
            await self._bot.send_message(config.LOGS_CHAT_ID, log_text)
        except Exception as exc:
            logging.error("Failed to log reminder instance send: %s", exc)
