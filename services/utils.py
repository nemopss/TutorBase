"""Utility functions for service layer operations.

This module contains helper functions used across service layer for common
operations like timezone normalization, lesson statistics calculation, package
metrics synchronization, and lesson generation from templates.

Key components:
    - normalize_to_utc: Convert datetime to UTC timezone
    - lesson_stats: Calculate lesson statistics (total, completed, cancelled)
    - sync_package_metrics: Synchronize package metrics from lessons
    - generate_lessons_from_template: Generate lessons based on template schedule

Business logic:
    - Package metrics are derived from lesson data (start/end dates, counts)
    - Lesson generation uses weekly schedule with timezone awareness
    - Statistics track lesson completion and cancellation rates
    - All timestamps normalized to UTC for storage

Usage:
    These utilities are called by service layer functions (package_service,
    lesson_service) to maintain data consistency and generate scheduled lessons.
"""
from __future__ import annotations

import heapq
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from zoneinfo import ZoneInfo

from api.dependencies import CurrentTenant

from database import crud
from database.models import Lesson, LessonPackage, LessonPackageTemplate
from utils.scheduling import parse_time


def normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to UTC timezone.

    Converts datetime to UTC, treating naive datetimes as already UTC.

    Args:
        dt: Datetime to normalize (None returns None)

    Returns:
        UTC datetime or None if input is None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def lesson_stats(lessons: Sequence[Lesson]) -> tuple[int, int, int]:
    """Calculate lesson statistics from lesson list.

    Counts total lessons and lessons by status (completed, cancelled).

    Args:
        lessons: Sequence of Lesson models

    Returns:
        Tuple of (total_count, completed_count, cancelled_count)
    """
    total = len(lessons)
    completed = sum(1 for lesson in lessons if lesson.status == 'completed')
    cancelled = sum(1 for lesson in lessons if lesson.status == 'cancelled')
    return total, completed, cancelled


async def sync_package_metrics(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
) -> tuple[Optional[LessonPackage], list[Lesson]]:
    """Synchronize package metrics from its lessons.

    Updates package total_lessons, start_date, and end_date based on current
    lesson data. Sorts lessons by scheduled time and derives package dates
    from first and last lessons.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Package ID to synchronize

    Returns:
        Tuple of (updated package or None, sorted lessons list)
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        return None, []

    lessons = sorted(
        package.lessons or [],
        key=lambda lesson: (normalize_to_utc(lesson.scheduled_at) or datetime.min.replace(tzinfo=timezone.utc)),
    )

    previous_price = package.price
    package.total_lessons = len(lessons)
    if lessons:
        package.start_date = normalize_to_utc(lessons[0].scheduled_at)
        package.end_date = normalize_to_utc(lessons[-1].scheduled_at)
    else:
        package.end_date = None

    # Auto-complete package if all lessons are completed or cancelled
    if lessons and package.status == 'active':
        all_done = all(
            lesson.status in ('completed', 'cancelled')
            for lesson in lessons
        )
        if all_done:
            package.status = 'completed'

    await session.flush([package])
    price_was_imputed = False
    if (
        package.package_type == "package"
        and package.total_lessons
        and package.total_lessons > 0
        and (previous_price is None or previous_price <= Decimal("0"))
        and package.learner is not None
        and package.learner.lesson_rate is not None
    ):
        from services.finance_service import calculate_package_price, update_payment_status

        calculated_price = calculate_package_price(package.learner.lesson_rate, package.total_lessons)
        if calculated_price is not None and calculated_price > Decimal("0"):
            package.price = calculated_price
            price_was_imputed = True
            await session.flush([package])
        if price_was_imputed:
            await update_payment_status(session, package.id)

    for lesson in lessons:
        lesson.package = package
    return package, lessons


async def generate_lessons_from_template(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    template: LessonPackageTemplate,
    start_date: datetime,
) -> None:
    """Generate lessons for package based on template schedule.

    Creates lessons according to template's weekly_schedule configuration.
    Schedule defines recurring weekly time slots (day of week + time). Lessons
    are generated up to template.lesson_count limit.

    Business logic:
        1. Parse weekly_schedule from template config
        2. Calculate lesson occurrences starting from start_date
        3. Create lesson records with sequence numbers
        4. Update package total_lessons and end_date

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package: Package to generate lessons for
        template: Template with schedule configuration
        start_date: Start date for lesson generation (timezone-aware)

    Example schedule config:
        {
            "weekly_schedule": [
                {"day": 0, "time": "10:00"},  # Monday 10:00
                {"day": 2, "time": "14:00"},  # Wednesday 14:00
            ]
        }
    """
    config = template.default_config or {}
    schedule = config.get('weekly_schedule') or []
    if not schedule:
        return

    lesson_limit = template.lesson_count or len(schedule)
    tz = ZoneInfo(package.timezone or template.default_timezone or 'Europe/Moscow')
    base_date = start_date.astimezone(tz)
    occurrences = _iter_weekly_occurrences(base_date, schedule, lesson_limit)

    for sequence, candidate in enumerate(occurrences, start=1):
        scheduled_utc = candidate.astimezone(timezone.utc)
        await crud.create_lesson(
            session,
            current_tenant,
            package,
            scheduled_at=scheduled_utc,
            sequence_index=sequence,
            duration_minutes=None,
        )

    if occurrences:
        last_lesson = occurrences[-1].astimezone(timezone.utc)
        await crud.update_lesson_package(
            session,
            package,
            total_lessons=len(occurrences),
            end_date=last_lesson,
        )


def _iter_weekly_occurrences(
    start_local: datetime,
    schedule: list[dict[str, object]],
    limit: int,
) -> list[datetime]:
    """Generate chronologically ordered lesson occurrences from weekly schedule.

    Uses min-heap to efficiently merge multiple weekly time slots into single
    chronological sequence. Each schedule item repeats weekly until limit reached.

    Algorithm:
        1. Initialize heap with first occurrence of each schedule item
        2. Pop earliest occurrence, add to results
        3. Push next week's occurrence back to heap
        4. Repeat until limit reached

    Args:
        start_local: Start datetime in local timezone
        schedule: List of schedule items with 'day' (0-6) and 'time' (HH:MM)
        limit: Maximum number of occurrences to generate

    Returns:
        List of datetime occurrences in chronological order
    """
    if limit <= 0:
        return []

    heap: list[tuple[datetime, dict[str, object]]] = []
    for item in schedule:
        day = item.get('day')
        time_str = item.get('time')
        if not isinstance(day, int) or not isinstance(time_str, str):
            continue
        try:
            lesson_time = parse_time(time_str)
        except ValueError:
            continue
        days_delta = (day - start_local.weekday()) % 7
        candidate = start_local + timedelta(days=days_delta)
        candidate = candidate.replace(
            hour=lesson_time.hour,
            minute=lesson_time.minute,
            second=0,
            microsecond=0,
        )
        if candidate < start_local:
            candidate += timedelta(days=7)
        heapq.heappush(heap, (candidate, {'day': day, 'time': time_str}))

    occurrences: list[datetime] = []
    while heap and len(occurrences) < limit:
        candidate, item = heapq.heappop(heap)
        occurrences.append(candidate)
        next_candidate = candidate + timedelta(days=7)
        if len(occurrences) < limit:
            heapq.heappush(heap, (next_candidate, item))
    return occurrences


__all__ = [
    "normalize_to_utc",
    "lesson_stats",
    "sync_package_metrics",
    "generate_lessons_from_template",
]
