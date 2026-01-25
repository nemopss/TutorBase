"""Reminder scheduler and delivery system for Telegram notifications.

This module implements the ReminderScheduler class which handles automated delivery
of reminders to learners via Telegram bot. The scheduler runs continuously, checking
for due reminder instances and sending appropriate messages.

Key components:
    - ReminderScheduler: Main scheduler class that processes reminder instances
    - start/stop: Lifecycle management for the scheduler task
    - _tick: Periodic check for due reminders (every 30 seconds)
    - _process_instance: Send individual reminder with error handling
    - _build_instance_message: Format reminder message based on type

Business logic:
    - Respects learner notification preferences (skips if disabled)
    - Handles Telegram errors (permanent vs temporary failures)
    - Retries temporary failures, marks permanent failures as failed
    - Sends admin notifications for permanent failures
    - Logs successful deliveries to admin chat
    - Supports multiple reminder types with custom messages and keyboards

Error handling:
    - TelegramBadRequest/TelegramForbiddenError: Permanent failures (user blocked bot)
    - Network errors: Temporary failures (retry later)
    - Missing chat identifier: Permanent failure
    - Empty message text: Permanent failure

Integration:
    - Uses crud layer for database operations
    - Integrates with Telegram bot via aiogram
    - Uses timezone-aware formatting for schedules
    - Sends notifications to configured admin chat
"""
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
from utils.formatters import escape_html_text, split_chat_identifier

from zoneinfo import ZoneInfo

from services.reminder_definitions import (
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_PAYMENT_WEEK,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
)

# Maximum retry attempts for temporary failures
MAX_RETRY_ATTEMPTS = 3

class ReminderScheduler:
    """Automated reminder scheduler for sending Telegram notifications.

    Runs as a background task that periodically checks for due reminder instances
    and sends them via Telegram bot. Handles error cases, retries, and logging.

    Attributes:
        _bot: Telegram bot instance for sending messages
        _task: Asyncio task running the scheduler loop
        _stop_event: Event to signal scheduler shutdown
    """

    def __init__(self, bot: Bot) -> None:
        """Initialize reminder scheduler with Telegram bot.

        Args:
            bot: Aiogram Bot instance for sending messages
        """
        self._bot = bot
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the reminder scheduler background task.

        Creates and starts the scheduler loop if not already running.
        Safe to call multiple times (idempotent).
        """
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._runner())

    async def stop(self) -> None:
        """Stop the reminder scheduler gracefully.

        Signals the scheduler to stop and waits for current iteration to complete.
        Safe to call if scheduler is not running.
        """
        if not self._task:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _runner(self) -> None:
        """Run the main scheduler loop continuously.

        Execute tick every 30 seconds to check for due reminders. Catch and
        log exceptions to prevent scheduler from crashing.
        """
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
        """Single scheduler iteration to process due reminders.

        Fetches current time and processes all due reminder instances in a
        database session.
        """
        now_utc = datetime.now(timezone.utc)
        async with async_session() as session:
            await self._process_instances(session, now_utc)

    async def _process_instances(self, session, now_utc: datetime) -> None:
        """Process all due reminder instances.

        Fetches all instances scheduled for delivery and processes each one
        individually. Commits successful deliveries and rolls back failures.

        Args:
            session: Database session for queries and updates
            now_utc: Current UTC time for due check
        """
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
        """Process and send a single reminder instance.

        Validates learner notification preferences, resolves chat target, builds
        message, sends via Telegram, and updates instance status. Handles various
        error cases with appropriate retry logic.

        Args:
            session: Database session for updates
            instance: ReminderInstance to process
            now_utc: Current UTC time for status updates
        """
        # Check if notifications are enabled for this learner
        if instance.learner and not instance.learner.notifications_enabled:
            logging.info(
                "Skipping reminder instance #%s: notifications disabled for learner #%s (%s)",
                instance.id,
                instance.learner.id,
                instance.learner.display_name,
            )
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='skipped',
                active=False,
                comment='Notifications disabled for learner',
            )
            return

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
            # Permanent error: invalid request
            await self._handle_instance_send_failure(
                session, instance, contact_display, 'TelegramBadRequest', exc, now_utc, is_permanent=True
            )
        except TelegramForbiddenError as exc:
            # Permanent error: bot blocked by user
            await self._handle_instance_send_failure(
                session, instance, contact_display, 'TelegramForbiddenError', exc, now_utc, is_permanent=True
            )
        except Exception as exc:
            # Temporary error: network issue, timeout, etc. - retry later
            await self._handle_instance_send_failure(
                session, instance, contact_display, 'NetworkError', exc, now_utc, is_permanent=False
            )
        else:
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='sent',
                active=False,
                last_notified_at=now_utc,
            )
            # Reset retry counter on success
            instance.retry_count = 0
            session.add(instance)
            await self._log_instance_sent(instance, schedule_label)

    async def _handle_instance_send_failure(
        self, 
        session, 
        instance, 
        contact_display: str, 
        reason: str, 
        exc: Exception, 
        now_utc: datetime,
        is_permanent: bool = True
    ) -> None:
        """Handle reminder send failure with appropriate retry logic.

        Distinguishes between permanent failures (user blocked bot, invalid request)
        and temporary failures (network issues). Permanent failures are marked as
        failed and deactivated. Temporary failures remain active for retry.

        Args:
            session: Database session for updates
            instance: Failed ReminderInstance
            contact_display: Display string for contact (for logging)
            reason: Failure reason category (TelegramBadRequest, NetworkError, etc)
            exc: Exception that caused the failure
            now_utc: Current UTC time
            is_permanent: Whether failure is permanent (default True)
        """
        if is_permanent:
            # Permanent failure: mark as failed and deactivate
            logging.error(
                "Permanent failure for reminder instance #%s to %s: %s (%s)",
                instance.id,
                contact_display,
                exc,
                reason,
            )
            comment = f"Permanent failure ({reason}): {exc}"[:1000]
            await crud.set_reminder_instance_status(
                session,
                instance,
                status='failed',
                active=False,
                comment=comment,
            )
        else:
            # Temporary failure: check retry limit
            retry_count = instance.retry_count + 1
            
            if retry_count >= MAX_RETRY_ATTEMPTS:
                # Max retries reached - mark as permanently failed
                logging.error(
                    "Max retries (%s) reached for reminder instance #%s to %s: %s (%s)",
                    MAX_RETRY_ATTEMPTS,
                    instance.id,
                    contact_display,
                    exc,
                    reason,
                )
                comment = f"Max retries ({MAX_RETRY_ATTEMPTS}) reached: {exc}"[:1000]
                await crud.set_reminder_instance_status(
                    session,
                    instance,
                    status='failed',
                    active=False,
                    comment=comment,
                )
                # Update retry counter
                instance.retry_count = retry_count
                session.add(instance)
                # Send admin notification (fall through to admin notification code)
            else:
                # Keep active for retry
                logging.warning(
                    "Temporary failure for reminder instance #%s to %s (attempt %s/%s): %s (%s) - will retry",
                    instance.id,
                    contact_display,
                    retry_count,
                    MAX_RETRY_ATTEMPTS,
                    exc,
                    reason,
                )
                comment = f"Retry {retry_count}/{MAX_RETRY_ATTEMPTS}: {exc}"[:1000]
                await crud.set_reminder_instance_status(
                    session,
                    instance,
                    status='pending',
                    active=True,  # Keep active for retry
                    comment=comment,
                )
                # Update retry counter
                instance.retry_count = retry_count
                session.add(instance)
                return  # Don't send admin notification for temporary failures (below limit)
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
        """Get human-readable description of reminder type.

        Maps reminder type constants to localized text labels.

        Args:
            instance: ReminderInstance to describe

        Returns:
            Localized reminder type description
        """
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
        """Extract student name from reminder instance.

        Checks payload first, then falls back to learner display name.

        Args:
            instance: ReminderInstance

        Returns:
            Student name or '—' if not available
        """
        payload = instance.payload or {}
        return payload.get('student_name') or (instance.learner.display_name if instance.learner else '—')

    def _resolve_instance_target(self, instance) -> Tuple[Optional[int | str], str]:
        """Resolve Telegram chat target from reminder instance.

        Extracts chat identifier from instance or learner's bot_user. Parses
        identifier to get actual chat ID (int or string).

        Args:
            instance: ReminderInstance with chat_identifier or learner

        Returns:
            Tuple of (chat_target, display_string) where chat_target is int or
            string for Telegram API, and display_string is for logging
        """
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
        """Build formatted schedule string for reminder message.

        Extracts schedule from lesson, payload, or instance scheduled_for field.
        Formats datetime with timezone awareness.

        Args:
            instance: ReminderInstance with schedule information

        Returns:
            Formatted schedule string (e.g., "2025-10-21 14:00 MSK")
        """
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
        """Format datetime with timezone conversion.

        Converts UTC datetime to specified timezone and formats as string.
        Falls back to Europe/Moscow if timezone is invalid.

        Args:
            dt: Datetime to format (assumed UTC if naive)
            tz_name: Target timezone name (e.g., "Europe/Moscow")

        Returns:
            Formatted datetime string with timezone abbreviation
        """
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo('Europe/Moscow')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        localized = dt.astimezone(tz)
        return localized.strftime('%Y-%m-%d %H:%M %Z')

    def _build_instance_message(self, instance, schedule_label: str) -> Tuple[Optional[str], Optional[InlineKeyboardMarkup]]:
        """Build reminder message text and keyboard based on type.

        Creates appropriate message and inline keyboard for each reminder type.
        Lesson reminders include confirm/decline buttons, payment reminders are
        text-only, etc.

        Args:
            instance: ReminderInstance to build message for
            schedule_label: Formatted schedule string

        Returns:
            Tuple of (message_text, keyboard_markup) where keyboard may be None
        """
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
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text=texts.PAYMENT_CONFIRM_BUTTON,
                callback_data=f"payment_confirm_{instance.id}"
            )
            keyboard.button(
                text=texts.PAYMENT_DECLINE_BUTTON,
                callback_data=f"payment_decline_{instance.id}"
            )
            keyboard.adjust(1)
            
            # Get last lesson date from payload
            last_lesson_date = payload.get('last_lesson_date', '—')
            
            message = texts.PAYMENT_REMINDER_WEEK_BEFORE.format(
                name=name,
                last_lesson_date=escape_html_text(last_lesson_date),
            )
            return message, keyboard.as_markup()

        if reminder_type == REMINDER_TYPE_PAYMENT_DAY:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text=texts.PAYMENT_CONFIRM_BUTTON,
                callback_data=f"payment_confirm_{instance.id}"
            )
            keyboard.button(
                text=texts.PAYMENT_DECLINE_BUTTON,
                callback_data=f"payment_decline_{instance.id}"
            )
            keyboard.adjust(1)
            
            message = texts.PAYMENT_REMINDER_DAY_BEFORE.format(name=name)
            return message, keyboard.as_markup()

        if reminder_type == REMINDER_TYPE_HOMEWORK:
            return (
                texts.HOMEWORK_REMINDER_MESSAGE.format(
                    name=name,
                    schedule=escape_html_text(schedule_label),
                ),
                None,
            )

        if reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text=texts.PAYMENT_CONFIRM_BUTTON,
                callback_data=f"payment_confirm_{instance.id}"
            )
            keyboard.button(
                text=texts.PAYMENT_DECLINE_BUTTON,
                callback_data=f"payment_decline_{instance.id}"
            )
            keyboard.adjust(1)
            
            end_label = payload.get('package_end') or schedule_label
            return (
                texts.PACKAGE_RENEWAL_REMINDER_MESSAGE.format(
                    name=name,
                    end_date=escape_html_text(end_label),
                ),
                keyboard.as_markup(),
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
        """Log successful reminder delivery to admin chat.

        Sends formatted log message to configured admin chat with reminder details.

        Args:
            instance: Successfully sent ReminderInstance
            schedule: Formatted schedule string for logging
        """
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
