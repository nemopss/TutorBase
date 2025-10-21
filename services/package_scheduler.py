"""Package reminder scheduler for automatic reminder generation.

This module handles the generation of reminder rules and instances for lesson
packages. When a package is created or updated, this scheduler creates all
necessary reminders based on lesson schedules.

Key components:
    - regenerate_package_reminders: Main entry point to rebuild all reminders
    - _create_lesson_confirm: Create confirmation reminders before lessons
    - _create_lesson_day_before_confirm: Create day-before reminders
    - _create_homework_reminder: Create homework reminders after lessons
    - _create_payment_reminders: Create payment reminders after last lesson
    - _create_package_renewal: Create package renewal reminder

Reminder types generated:
    - Lesson confirmation: Sent N minutes before lesson (default 60 min)
    - Day-before reminder: Sent day before at specific time (10:00)
    - Homework reminder: Sent day before next lesson at specific time (10:00)
    - Payment reminders: Week and day before last lesson
    - Package renewal: Sent 14 days before package end

Business logic:
    - All reminders are timezone-aware using package timezone
    - Past reminders are marked as 'expired' and inactive
    - Future reminders are marked as 'scheduled' and active
    - Reminders without valid schedule are marked as 'cancelled'
    - Regenerating clears all existing reminders and creates new ones

Integration:
    - Called by package_service when package is created/updated
    - Creates ReminderRule and ReminderInstance records
    - Used by reminder scheduler (reminders.py) for delivery
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from api.dependencies import CurrentTenant
from database import crud
from database.models import LessonPackage, Lesson, ReminderRule
from services.reminder_definitions import (
    DEFAULT_LESSON_CONFIRM_LEAD_MINUTES,
    LESSON_DAY_BEFORE_LEAD_DAYS,
    LESSON_DAY_BEFORE_SEND_HOUR,
    LESSON_DAY_BEFORE_SEND_MINUTE,
    HOMEWORK_LEAD_DAYS,
    HOMEWORK_SEND_HOUR,
    HOMEWORK_SEND_MINUTE,
    PACKAGE_RENEWAL_LEAD_DAYS,
    PACKAGE_RENEWAL_SEND_HOUR,
    PACKAGE_RENEWAL_SEND_MINUTE,
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_PAYMENT_WEEK,
)
from utils.formatters import pack_chat_identifier


@dataclass
class _ReminderSchedule:
    """Internal dataclass for reminder scheduling metadata.

    Attributes:
        scheduled_for: UTC datetime when reminder should be sent (None if cancelled)
        status: Reminder status ('scheduled', 'expired', 'cancelled')
        active: Whether reminder is active for delivery
    """

    scheduled_for: Optional[datetime]
    status: str
    active: bool


async def regenerate_package_reminders(session: AsyncSession, current_tenant: CurrentTenant, package: LessonPackage) -> None:
    """Rebuild all reminder rules and instances for a package.

    Clears existing reminders and creates new ones based on current lesson schedule.
    Generates multiple reminder types for each lesson (confirmation, day-before,
    homework) plus payment and renewal reminders for the package.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package: LessonPackage to generate reminders for

    Raises:
        ValueError: If package is not found after refresh
    """
    package_id = package.id
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if package is None:
        raise ValueError(f"Package #{package_id} not found")

    if not package.learner:
        return

    await _clear_existing(session, package)

    lessons = sorted(
        [lesson for lesson in package.lessons or [] if lesson.scheduled_at],
        key=lambda lesson: _normalize_datetime(lesson.scheduled_at),
    )
    now_utc = datetime.now(timezone.utc)
    tz = _package_tz(package)
    chat_identifier = _preferred_chat_identifier(package)

    for lesson in lessons:
        await _create_lesson_confirm(session, current_tenant, package, lesson, tz, chat_identifier, now_utc)
        await _create_lesson_day_before_confirm(session, current_tenant, package, lesson, tz, chat_identifier, now_utc)
        await _create_homework_reminder(session, current_tenant, package, lesson, tz, chat_identifier, now_utc)

    if lessons:
        last_lesson = lessons[-1]
        await _create_payment_reminders(session, current_tenant, package, last_lesson, tz, chat_identifier, now_utc)

    await _create_package_renewal(session, current_tenant, package, lessons, tz, chat_identifier, now_utc)


async def _clear_existing(session: AsyncSession, package: LessonPackage) -> None:
    """Delete all existing reminder rules and instances for package.

    Args:
        session: Async database session
        package: Package to clear reminders from
    """
    for rule in list(package.reminder_rules or []):
        await session.delete(rule)
    for instance in list(package.reminder_instances or []):
        await session.delete(instance)
    await session.flush()


def _package_tz(package: LessonPackage) -> ZoneInfo:
    """Get timezone for package with fallback to Europe/Moscow.

    Args:
        package: Package to get timezone from

    Returns:
        ZoneInfo for package timezone or Europe/Moscow if invalid
    """
    tz_name = package.timezone or 'Europe/Moscow'
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo('Europe/Moscow')


def _preferred_chat_identifier(package: LessonPackage) -> Optional[str]:
    """Get chat identifier for learner from package.

    Args:
        package: Package with learner

    Returns:
        Packed chat identifier string or None if no learner
    """
    learner = package.learner
    if not learner:
        return None
    if learner.bot_user and learner.bot_user.chat_id:
        return pack_chat_identifier(learner.display_name, str(learner.bot_user.chat_id))
    return pack_chat_identifier(learner.display_name, learner.display_name)


async def _create_lesson_confirm(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    """Create lesson confirmation reminder (sent before lesson).

    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Package containing lesson
        lesson: Lesson to create reminder for
        tz: Timezone for scheduling
        chat_identifier: Chat identifier for delivery
        now_utc: Current UTC time for status determination
    """
    rule = await crud.create_reminder_rule(
        session,
        current_tenant,
        package=package,
        lesson=lesson,
        reminder_type=REMINDER_TYPE_LESSON_CONFIRM,
        config={'offset_minutes': DEFAULT_LESSON_CONFIRM_LEAD_MINUTES},
    )

    scheduled = _compute_lesson_offset(lesson, tz, minutes=-DEFAULT_LESSON_CONFIRM_LEAD_MINUTES)
    schedule_meta = _resolve_schedule_state(scheduled, now_utc)
    payload = {
        'student_name': package.learner.display_name,
        'lesson_id': lesson.id,
        'sequence_index': lesson.sequence_index,
        'lead_minutes': DEFAULT_LESSON_CONFIRM_LEAD_MINUTES,
    }

    await crud.create_reminder_instance(
        session,
        current_tenant,
        rule=rule,
        package=package,
        learner=package.learner,
        lesson=lesson,
        scheduled_for=schedule_meta.scheduled_for or now_utc,
        status=schedule_meta.status,
        active=schedule_meta.active,
        payload=payload,
        chat_identifier=chat_identifier,
    )


async def _create_lesson_day_before_confirm(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    """Create day-before lesson confirmation reminder.

    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Package containing lesson
        lesson: Lesson to create reminder for
        tz: Timezone for scheduling
        chat_identifier: Chat identifier for delivery
        now_utc: Current UTC time for status determination
    """
    rule = await crud.create_reminder_rule(
        session,
        current_tenant,
        package=package,
        lesson=lesson,
        reminder_type=REMINDER_TYPE_LESSON_DAY_BEFORE,
        config={
            'send_time': f"{LESSON_DAY_BEFORE_SEND_HOUR:02d}:{LESSON_DAY_BEFORE_SEND_MINUTE:02d}",
            'lead_days': LESSON_DAY_BEFORE_LEAD_DAYS,
        },
    )

    scheduled = _compute_day_before_confirm_time(lesson, tz)
    schedule_meta = _resolve_schedule_state(scheduled, now_utc)
    payload = {
        'student_name': package.learner.display_name,
        'lesson_id': lesson.id,
        'sequence_index': lesson.sequence_index,
        'lead_minutes': LESSON_DAY_BEFORE_LEAD_DAYS * 24 * 60,
    }

    await crud.create_reminder_instance(
        session,
        current_tenant,
        rule=rule,
        package=package,
        learner=package.learner,
        lesson=lesson,
        scheduled_for=schedule_meta.scheduled_for or now_utc,
        status=schedule_meta.status,
        active=schedule_meta.active,
        payload=payload,
        chat_identifier=chat_identifier,
    )


async def _create_homework_reminder(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    """Create homework reminder (sent day before next lesson).

    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Package containing lesson
        lesson: Lesson to create reminder for
        tz: Timezone for scheduling
        chat_identifier: Chat identifier for delivery
        now_utc: Current UTC time for status determination
    """
    rule = await crud.create_reminder_rule(
        session,
        current_tenant,
        package=package,
        lesson=lesson,
        reminder_type=REMINDER_TYPE_HOMEWORK,
        config={
            'send_time': f"{HOMEWORK_SEND_HOUR:02d}:{HOMEWORK_SEND_MINUTE:02d}",
            'lead_days': HOMEWORK_LEAD_DAYS,
        },
    )

    scheduled = _compute_homework_time(lesson, tz)
    schedule_meta = _resolve_schedule_state(scheduled, now_utc)
    payload = {
        'student_name': package.learner.display_name,
        'lesson_id': lesson.id,
        'sequence_index': lesson.sequence_index,
        'lead_minutes': HOMEWORK_LEAD_DAYS * 24 * 60,
    }

    await crud.create_reminder_instance(
        session,
        current_tenant,
        rule=rule,
        package=package,
        learner=package.learner,
        lesson=lesson,
        scheduled_for=schedule_meta.scheduled_for or now_utc,
        status=schedule_meta.status,
        active=schedule_meta.active,
        payload=payload,
        chat_identifier=chat_identifier,
    )


async def _create_payment_reminders(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    last_lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    """Create payment reminders (week and day before last lesson).

    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Package for reminders
        last_lesson: Last lesson in package
        tz: Timezone for scheduling
        chat_identifier: Chat identifier for delivery
        now_utc: Current UTC time for status determination
    """
    for reminder_type, delta in (
        (REMINDER_TYPE_PAYMENT_WEEK, timedelta(weeks=1)),
        (REMINDER_TYPE_PAYMENT_DAY, timedelta(days=1)),
    ):
        rule = await crud.create_reminder_rule(
            session,
            current_tenant,
            package=package,
            lesson=None,
            reminder_type=reminder_type,
            config={},
        )

        scheduled = _compute_payment_time(last_lesson, tz, delta)
        schedule_meta = _resolve_schedule_state(scheduled, now_utc)
        payload = {
            'student_name': package.learner.display_name,
            'lesson_id': last_lesson.id,
        }

        await crud.create_reminder_instance(
            session,
            current_tenant,
            rule=rule,
            package=package,
            learner=package.learner,
            lesson=last_lesson,
            scheduled_for=schedule_meta.scheduled_for or now_utc,
            status=schedule_meta.status,
            active=schedule_meta.active,
            payload=payload,
            chat_identifier=chat_identifier,
        )


async def _create_package_renewal(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    lessons: Iterable[Lesson],
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    """Create package renewal reminder (14 days before end).

    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Package for renewal reminder
        lessons: All lessons in package
        tz: Timezone for scheduling
        chat_identifier: Chat identifier for delivery
        now_utc: Current UTC time for status determination
    """
    reference = package.end_date
    if not reference:
        lessons = list(lessons)
        if lessons:
            reference = lessons[-1].scheduled_at
    if not reference:
        return

    rule = await crud.create_reminder_rule(
        session,
        current_tenant,
        package=package,
        lesson=None,
        reminder_type=REMINDER_TYPE_PACKAGE_RENEWAL,
        config={'lead_days': PACKAGE_RENEWAL_LEAD_DAYS},
    )

    scheduled = _compute_package_renewal_time(reference, tz)
    schedule_meta = _resolve_schedule_state(scheduled, now_utc)
    payload = {
        'student_name': package.learner.display_name,
        'package_end': _format_local(reference, tz),
    }

    await crud.create_reminder_instance(
        session,
        current_tenant,
        rule=rule,
        package=package,
        learner=package.learner,
        lesson=None,
        scheduled_for=schedule_meta.scheduled_for or now_utc,
        status=schedule_meta.status,
        active=schedule_meta.active,
        payload=payload,
        chat_identifier=chat_identifier,
    )


def _compute_lesson_offset(lesson: Lesson, tz: ZoneInfo, *, minutes: int) -> Optional[datetime]:
    """Compute reminder time as offset from lesson time.

    Args:
        lesson: Lesson to compute offset from
        tz: Timezone for calculation
        minutes: Offset in minutes (negative for before lesson)

    Returns:
        UTC datetime for reminder or None if lesson has no schedule
    """
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    reminder_local = lesson_local + timedelta(minutes=minutes)
    return reminder_local.astimezone(timezone.utc)


def _compute_homework_time(lesson: Lesson, tz: ZoneInfo) -> Optional[datetime]:
    """Compute homework reminder time (day before at specific hour).

    Args:
        lesson: Lesson to compute homework reminder for
        tz: Timezone for calculation

    Returns:
        UTC datetime for homework reminder or None if lesson has no schedule
    """
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    homework_day = lesson_local - timedelta(days=HOMEWORK_LEAD_DAYS)
    homework_local = homework_day.replace(hour=HOMEWORK_SEND_HOUR, minute=HOMEWORK_SEND_MINUTE, second=0, microsecond=0)
    return homework_local.astimezone(timezone.utc)


def _compute_day_before_confirm_time(lesson: Lesson, tz: ZoneInfo) -> Optional[datetime]:
    """Compute day-before confirmation time (day before at specific hour).

    Args:
        lesson: Lesson to compute reminder for
        tz: Timezone for calculation

    Returns:
        UTC datetime for day-before reminder or None if lesson has no schedule
    """
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    reminder_day = lesson_local - timedelta(days=LESSON_DAY_BEFORE_LEAD_DAYS)
    reminder_local = reminder_day.replace(
        hour=LESSON_DAY_BEFORE_SEND_HOUR,
        minute=LESSON_DAY_BEFORE_SEND_MINUTE,
        second=0,
        microsecond=0,
    )
    return reminder_local.astimezone(timezone.utc)


def _compute_payment_time(lesson: Lesson, tz: ZoneInfo, delta: timedelta) -> Optional[datetime]:
    """Compute payment reminder time (offset before last lesson).

    Args:
        lesson: Last lesson to compute payment reminder from
        tz: Timezone for calculation
        delta: Time delta before lesson (e.g., 1 week, 1 day)

    Returns:
        UTC datetime for payment reminder or None if lesson has no schedule
    """
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    payment_local = lesson_local - delta
    return payment_local.astimezone(timezone.utc)


def _compute_package_renewal_time(reference: datetime, tz: ZoneInfo) -> Optional[datetime]:
    """Compute package renewal reminder time (14 days before end at specific hour).

    Args:
        reference: Package end date or last lesson date
        tz: Timezone for calculation

    Returns:
        UTC datetime for renewal reminder or None
    """
    reference_local = _to_local(reference, tz)
    reminder_local = reference_local - timedelta(days=PACKAGE_RENEWAL_LEAD_DAYS)
    reminder_local = reminder_local.replace(hour=PACKAGE_RENEWAL_SEND_HOUR, minute=PACKAGE_RENEWAL_SEND_MINUTE, second=0, microsecond=0)
    return reminder_local.astimezone(timezone.utc)


def _resolve_schedule_state(scheduled_for: Optional[datetime], now_utc: datetime) -> _ReminderSchedule:
    """Determine reminder status and active state based on schedule time.

    Args:
        scheduled_for: Scheduled UTC datetime or None
        now_utc: Current UTC time

    Returns:
        _ReminderSchedule with status and active flag
    """
    if scheduled_for is None:
        return _ReminderSchedule(scheduled_for=None, status='cancelled', active=False)
    if scheduled_for <= now_utc:
        return _ReminderSchedule(scheduled_for=scheduled_for, status='expired', active=False)
    return _ReminderSchedule(scheduled_for=scheduled_for, status='scheduled', active=True)


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert datetime to local timezone.

    Args:
        dt: Datetime to convert (assumed UTC if naive)
        tz: Target timezone

    Returns:
        Datetime in target timezone
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return dt.astimezone(tz)


def _format_local(dt: datetime, tz: ZoneInfo) -> str:
    """Format datetime as local date string.

    Args:
        dt: Datetime to format
        tz: Timezone for formatting

    Returns:
        Date string in YYYY-MM-DD format
    """
    return _to_local(dt, tz).strftime('%Y-%m-%d')


def _normalize_datetime(dt: Optional[datetime]) -> datetime:
    """Normalize datetime to UTC for sorting.

    Args:
        dt: Datetime to normalize (None becomes datetime.min)

    Returns:
        UTC datetime for comparison
    """
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
