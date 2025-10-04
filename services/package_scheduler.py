"""Utilities for generating reminder rules and instances for lesson packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from database import crud
from database.models import LessonPackage, Lesson, ReminderRule
from services.reminder_definitions import (
    DEFAULT_LESSON_CONFIRM_LEAD_MINUTES,
    HOMEWORK_LEAD_DAYS,
    HOMEWORK_SEND_HOUR,
    HOMEWORK_SEND_MINUTE,
    PACKAGE_RENEWAL_LEAD_DAYS,
    PACKAGE_RENEWAL_SEND_HOUR,
    PACKAGE_RENEWAL_SEND_MINUTE,
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_PAYMENT_WEEK,
    PAYMENT_TEMPLATE_DAY,
    PAYMENT_TEMPLATE_WEEK,
)
from utils.formatters import pack_chat_identifier


@dataclass
class _ReminderSchedule:
    scheduled_for: Optional[datetime]
    status: str
    active: bool


async def regenerate_package_reminders(session: AsyncSession, package: LessonPackage) -> None:
    """Rebuild reminder rules and instances for the package based on its lessons."""
    package = await crud.get_lesson_package(session, package.id)
    if package is None:
        raise ValueError(f"Package #{package.id} not found")

    if not package.learner:
        # Nothing to schedule without learner metadata
        return

    await _clear_existing(session, package)

    lessons = sorted([lesson for lesson in package.lessons or [] if lesson.scheduled_at], key=lambda l: l.scheduled_at)
    now_utc = datetime.now(timezone.utc)
    tz = _package_tz(package)
    chat_identifier = _preferred_chat_identifier(package)

    for lesson in lessons:
        await _create_lesson_confirm(session, package, lesson, tz, chat_identifier, now_utc)
        await _create_homework_reminder(session, package, lesson, tz, chat_identifier, now_utc)

    if lessons:
        last_lesson = lessons[-1]
        await _create_payment_reminders(session, package, last_lesson, tz, chat_identifier, now_utc)

    await _create_package_renewal(session, package, lessons, tz, chat_identifier, now_utc)


async def _clear_existing(session: AsyncSession, package: LessonPackage) -> None:
    # Delete rules (instances cascade)
    for rule in list(package.reminder_rules or []):
        await session.delete(rule)
    for instance in list(package.reminder_instances or []):
        await session.delete(instance)
    await session.flush()


def _package_tz(package: LessonPackage) -> ZoneInfo:
    tz_name = package.timezone or 'Europe/Moscow'
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo('Europe/Moscow')


def _preferred_chat_identifier(package: LessonPackage) -> Optional[str]:
    learner = package.learner
    if not learner:
        return None
    if learner.bot_user and learner.bot_user.chat_id:
        return pack_chat_identifier(learner.display_name, str(learner.bot_user.chat_id))
    return pack_chat_identifier(learner.display_name, learner.display_name)


async def _create_lesson_confirm(
    session: AsyncSession,
    package: LessonPackage,
    lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    rule = await crud.create_reminder_rule(
        session,
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
    package: LessonPackage,
    lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    rule = await crud.create_reminder_rule(
        session,
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
    package: LessonPackage,
    last_lesson: Lesson,
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    for reminder_type, template_key, delta in (
        (REMINDER_TYPE_PAYMENT_WEEK, PAYMENT_TEMPLATE_WEEK, timedelta(weeks=1)),
        (REMINDER_TYPE_PAYMENT_DAY, PAYMENT_TEMPLATE_DAY, timedelta(days=1)),
    ):
        rule = await crud.create_reminder_rule(
            session,
            package=package,
            lesson=None,
            reminder_type=reminder_type,
            config={'template_key': template_key},
        )

        scheduled = _compute_payment_time(last_lesson, tz, delta)
        schedule_meta = _resolve_schedule_state(scheduled, now_utc)
        payload = {
            'student_name': package.learner.display_name,
            'lesson_id': last_lesson.id,
            'template_key': template_key,
        }

        await crud.create_reminder_instance(
            session,
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
    package: LessonPackage,
    lessons: Iterable[Lesson],
    tz: ZoneInfo,
    chat_identifier: Optional[str],
    now_utc: datetime,
) -> None:
    reference = package.end_date
    if not reference:
        lessons = list(lessons)
        if lessons:
            reference = lessons[-1].scheduled_at
    if not reference:
        return

    rule = await crud.create_reminder_rule(
        session,
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
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    reminder_local = lesson_local + timedelta(minutes=minutes)
    return reminder_local.astimezone(timezone.utc)


def _compute_homework_time(lesson: Lesson, tz: ZoneInfo) -> Optional[datetime]:
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    homework_day = lesson_local - timedelta(days=HOMEWORK_LEAD_DAYS)
    homework_local = homework_day.replace(hour=HOMEWORK_SEND_HOUR, minute=HOMEWORK_SEND_MINUTE, second=0, microsecond=0)
    return homework_local.astimezone(timezone.utc)


def _compute_payment_time(lesson: Lesson, tz: ZoneInfo, delta: timedelta) -> Optional[datetime]:
    if not lesson.scheduled_at:
        return None
    lesson_local = _to_local(lesson.scheduled_at, tz)
    payment_local = lesson_local - delta
    return payment_local.astimezone(timezone.utc)


def _compute_package_renewal_time(reference: datetime, tz: ZoneInfo) -> Optional[datetime]:
    reference_local = _to_local(reference, tz)
    reminder_local = reference_local - timedelta(days=PACKAGE_RENEWAL_LEAD_DAYS)
    reminder_local = reminder_local.replace(hour=PACKAGE_RENEWAL_SEND_HOUR, minute=PACKAGE_RENEWAL_SEND_MINUTE, second=0, microsecond=0)
    return reminder_local.astimezone(timezone.utc)


def _resolve_schedule_state(scheduled_for: Optional[datetime], now_utc: datetime) -> _ReminderSchedule:
    if scheduled_for is None:
        return _ReminderSchedule(scheduled_for=None, status='cancelled', active=False)
    if scheduled_for <= now_utc:
        return _ReminderSchedule(scheduled_for=scheduled_for, status='expired', active=False)
    return _ReminderSchedule(scheduled_for=scheduled_for, status='scheduled', active=True)


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return dt.astimezone(tz)


def _format_local(dt: datetime, tz: ZoneInfo) -> str:
    return _to_local(dt, tz).strftime('%Y-%m-%d')
