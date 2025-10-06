from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import Lesson
from services.dto import LessonDTO
from services.exceptions import NotFoundError
from services.utils import sync_package_metrics


def _build_lesson_dto(lesson: Lesson) -> LessonDTO:
    return LessonDTO(
        id=lesson.id,
        package_id=lesson.package_id,
        scheduled_at=lesson.scheduled_at,
        status=lesson.status,
        duration_minutes=lesson.duration_minutes,
        sequence_index=lesson.sequence_index,
        teacher_notes=lesson.teacher_notes,
        homework_due_at=lesson.homework_due_at,
    )


async def get_lesson(session: AsyncSession, lesson_id: int) -> LessonDTO:
    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    return _build_lesson_dto(lesson)


async def update_lesson(
    session: AsyncSession,
    lesson_id: int,
    *,
    scheduled_at: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    status: Optional[str] = None,
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
) -> LessonDTO:
    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    if scheduled_at is not None:
        lesson.scheduled_at = scheduled_at
    if duration_minutes is not None or duration_minutes is None:
        lesson.duration_minutes = duration_minutes
    if status is not None:
        lesson.status = status
    if teacher_notes is not None:
        lesson.teacher_notes = teacher_notes
    if homework_due_at is not None or homework_due_at is None:
        lesson.homework_due_at = homework_due_at

    await session.flush([lesson])
    await sync_package_metrics(session, lesson.package_id)
    return _build_lesson_dto(lesson)


async def delete_lesson(session: AsyncSession, lesson_id: int) -> None:
    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    package_id = lesson.package_id
    await crud.delete_lesson(session, lesson)
    await sync_package_metrics(session, package_id)


async def create_lesson(
    session: AsyncSession,
    package_id: int,
    *,
    scheduled_at: datetime,
    duration_minutes: Optional[int] = None,
    status: str = 'scheduled',
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
    sequence_index: Optional[int] = None,
) -> LessonDTO:
    package = await crud.get_lesson_package(session, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")

    lesson = await crud.create_lesson(
        session,
        package,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        status=status,
        teacher_notes=teacher_notes,
        homework_due_at=homework_due_at,
        sequence_index=sequence_index,
    )
    await sync_package_metrics(session, package_id)
    return _build_lesson_dto(lesson)


async def list_lessons(session: AsyncSession, package_id: int) -> list[LessonDTO]:
    package = await crud.get_lesson_package(session, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    lessons = await crud.fetch_lessons_for_package(session, package_id)
    return [_build_lesson_dto(lesson) for lesson in lessons]


async def list_all_lessons(
    session: AsyncSession,
    *, 
    status: Optional[str] = None, 
    limit: int = 100, 
    offset: int = 0,
    sort_by: str = 'scheduled_at',
    sort_order: str = 'asc',
) -> list[LessonDTO]:
    lessons = await crud.list_all_lessons(
        session, 
        status=status, 
        limit=limit, 
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [_build_lesson_dto(lesson) for lesson in lessons]


__all__ = [
    "get_lesson",
    "update_lesson",
    "delete_lesson",
    "create_lesson",
    "list_lessons",
    "list_all_lessons",
]
