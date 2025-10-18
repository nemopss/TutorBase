from __future__ import annotations

import heapq
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence

from zoneinfo import ZoneInfo

from api.dependencies import CurrentTenant

from database import crud
from database.models import Lesson, LessonPackage, LessonPackageTemplate
from utils.scheduling import parse_time


def normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def lesson_stats(lessons: Sequence[Lesson]) -> tuple[int, int, int]:
    total = len(lessons)
    completed = sum(1 for lesson in lessons if lesson.status == 'completed')
    cancelled = sum(1 for lesson in lessons if lesson.status == 'cancelled')
    return total, completed, cancelled


async def sync_package_metrics(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
) -> tuple[Optional[LessonPackage], list[Lesson]]:
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        return None, []

    lessons = sorted(
        package.lessons or [],
        key=lambda lesson: (normalize_to_utc(lesson.scheduled_at) or datetime.min.replace(tzinfo=timezone.utc)),
    )

    package.total_lessons = len(lessons)
    if lessons:
        package.start_date = normalize_to_utc(lessons[0].scheduled_at)
        package.end_date = normalize_to_utc(lessons[-1].scheduled_at)
    else:
        package.end_date = None

    await session.flush([package])
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
