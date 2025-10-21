"""Service for managing lessons in the system.

This module contains business logic for working with lessons, including creation,
updates, deletion, and retrieval. All operations automatically synchronize parent
package metrics and respect multi-tenancy data isolation.

Key components:
    - create_lesson: Create a new lesson in a package
    - get_lesson: Retrieve a lesson by ID
    - update_lesson: Update lesson parameters
    - delete_lesson: Delete a lesson with metric synchronization
    - list_lessons: Get list of lessons for a package
    - list_all_lessons: Get all lessons with filtering and pagination

Business logic:
    - When creating/updating/deleting a lesson, package metrics are automatically
      recalculated (lesson count, statuses, progress)
    - All timestamps are normalized to the default timezone
    - Lessons are always tied to a package and learner through the package
    - Various lesson statuses are supported (scheduled, completed, cancelled)

Edge cases:
    - When deleting a lesson, package_id is returned for UI updates
    - If package is not found when creating a lesson, NotFoundError is raised
    - All operations are isolated by tenant_id for multi-tenancy
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from api.dependencies import CurrentTenant
from database import crud
from database.models import Lesson
from services.dto import LessonDTO
from services.exceptions import NotFoundError
from services.utils import sync_package_metrics
from utils.timezone import DEFAULT_TIMEZONE, normalize_to_timezone


def _build_lesson_dto(lesson: Lesson) -> LessonDTO:
    """Convert Lesson model to LessonDTO for data transfer.

    Extract related data from package and learner, normalize timestamps to
    default timezone. Safely handle missing relationships.

    Args:
        lesson: Lesson model object from database with loaded relationships

    Returns:
        LessonDTO with complete lesson data, including package title and learner name

    Note:
        Function safely handles cases where package or learner may be None,
        returning None for corresponding fields in DTO.
    """
    package_title = lesson.package.title if lesson.package else None
    learner_name = lesson.package.learner.display_name if lesson.package and lesson.package.learner else None
    
    return LessonDTO(
        id=lesson.id,
        package_id=lesson.package_id,
        package_title=package_title,
        learner_name=learner_name,
        scheduled_at=normalize_to_timezone(lesson.scheduled_at),
        status=lesson.status,
        duration_minutes=lesson.duration_minutes,
        sequence_index=lesson.sequence_index,
        teacher_notes=lesson.teacher_notes,
        homework_due_at=normalize_to_timezone(lesson.homework_due_at),
        timezone=DEFAULT_TIMEZONE,
    )


async def get_lesson(session: AsyncSession, current_tenant: CurrentTenant, lesson_id: int) -> LessonDTO:
    """Retrieve a lesson by ID with tenant isolation.

    Load lesson from database along with related data (package, learner)
    and convert to DTO for API layer transfer.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        lesson_id: ID of the lesson to retrieve

    Returns:
        LessonDTO with complete lesson data

    Raises:
        NotFoundError: If lesson with specified ID is not found or does not
            belong to current tenant
    """
    lesson = await crud.get_lesson(session, current_tenant, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    return _build_lesson_dto(lesson)


async def update_lesson(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    lesson_id: int,
    *,
    scheduled_at: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    status: Optional[str] = None,
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
) -> LessonDTO:
    """Update parameters of an existing lesson.

    Update specified lesson fields and automatically synchronize parent
    package metrics. Support partial updates - only provided parameters
    will be changed.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        lesson_id: ID of the lesson to update
        scheduled_at: New lesson scheduled time (optional)
        duration_minutes: New lesson duration in minutes (optional)
        status: New lesson status (scheduled/completed/cancelled) (optional)
        teacher_notes: Teacher notes (optional)
        homework_due_at: Homework due date (optional)

    Returns:
        LessonDTO with updated lesson data

    Raises:
        NotFoundError: If lesson with specified ID is not found or does not
            belong to current tenant

    Note:
        After update, package metrics are automatically recalculated
        (completed lesson count, progress, etc.)
    """
    lesson = await crud.get_lesson(session, current_tenant, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    if scheduled_at is not None:
        lesson.scheduled_at = scheduled_at
    if duration_minutes is not None:
        lesson.duration_minutes = duration_minutes
    if status is not None:
        lesson.status = status
    if teacher_notes is not None:
        lesson.teacher_notes = teacher_notes
    if homework_due_at is not None:
        lesson.homework_due_at = homework_due_at

    await session.flush([lesson])
    await sync_package_metrics(session, current_tenant, lesson.package_id)
    return _build_lesson_dto(lesson)


async def delete_lesson(session: AsyncSession, current_tenant: CurrentTenant, lesson_id: int) -> int:
    """Delete a lesson and synchronize package metrics.

    Remove lesson from database and automatically recalculate parent
    package metrics. Return package ID for UI updates.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        lesson_id: ID of the lesson to delete

    Returns:
        ID of the package that contained the deleted lesson (for UI updates)

    Raises:
        NotFoundError: If lesson with specified ID is not found or does not
            belong to current tenant

    Note:
        Function commits transaction after deletion and metric synchronization.
        Returning package_id allows client to update package display after
        lesson deletion.
    """
    lesson = await crud.get_lesson(session, current_tenant, lesson_id)
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    package_id = lesson.package_id
    
    delete_stmt = delete(Lesson).where(Lesson.id == lesson_id)
    await session.execute(delete_stmt)
    await sync_package_metrics(session, current_tenant, package_id)
    await session.commit()
    return package_id


async def create_lesson(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
    *,
    scheduled_at: datetime,
    duration_minutes: Optional[int] = None,
    status: str = 'scheduled',
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
    sequence_index: Optional[int] = None,
) -> LessonDTO:
    """Create a new lesson in the specified package.

    Create lesson with given parameters and automatically synchronize
    parent package metrics. Verify package existence before creating lesson.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        package_id: ID of the package to add lesson to
        scheduled_at: Scheduled lesson time (required)
        duration_minutes: Lesson duration in minutes (optional)
        status: Lesson status (default 'scheduled')
        teacher_notes: Teacher notes (optional)
        homework_due_at: Homework due date (optional)
        sequence_index: Lesson sequence number in package (optional)

    Returns:
        LessonDTO with created lesson data

    Raises:
        NotFoundError: If package with specified ID is not found or does not
            belong to current tenant

    Note:
        After lesson creation, package metrics are automatically recalculated.
        If sequence_index is not specified, it will be calculated automatically
        based on existing lessons in the package.
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")

    lesson = await crud.create_lesson(
        session,
        current_tenant,
        package,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        status=status,
        teacher_notes=teacher_notes,
        homework_due_at=homework_due_at,
        sequence_index=sequence_index,
    )
    await sync_package_metrics(session, current_tenant, package_id)
    return _build_lesson_dto(lesson)


async def list_lessons(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> list[LessonDTO]:
    """Retrieve list of all lessons for specified package.

    Load all lessons belonging to package and convert them to DTOs.
    Verify package existence before retrieving lessons.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        package_id: ID of the package to get lessons for

    Returns:
        List of LessonDTO with all package lessons, sorted by
        sequence_index or scheduled_at

    Raises:
        NotFoundError: If package with specified ID is not found or does not
            belong to current tenant
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    lessons = await crud.fetch_lessons_for_package(session, current_tenant, package_id)
    return [_build_lesson_dto(lesson) for lesson in lessons]


async def list_all_lessons(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *, 
    status: Optional[str] = None, 
    search: Optional[str] = None,
    limit: int = 100, 
    offset: int = 0,
    sort_by: str = 'scheduled_at',
    sort_order: str = 'asc',
) -> tuple[list[LessonDTO], int]:
    """Retrieve list of all lessons with filtering, search and pagination.

    Load lessons from all packages of current tenant with ability to filter
    by status, search by learner name or package title, sort and paginate results.

    Args:
        session: Async database session
        current_tenant: Current tenant context for data isolation
        status: Filter by lesson status (scheduled/completed/cancelled) (optional)
        search: Search query to filter by learner name or package title (optional)
        limit: Maximum number of lessons in result (default 100)
        offset: Offset for pagination (default 0)
        sort_by: Field to sort by (default 'scheduled_at')
        sort_order: Sort order 'asc' or 'desc' (default 'asc')

    Returns:
        Tuple of two elements:
            - List of LessonDTO with lessons matching criteria
            - Total count of lessons (without limit/offset) for pagination

    Note:
        Search is performed on learner.display_name and package.title fields.
        All lessons are automatically filtered by current user's tenant_id.
    """
    lessons, total = await crud.list_all_lessons(
        session, 
        current_tenant,
        status=status, 
        search=search,
        limit=limit, 
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [_build_lesson_dto(lesson) for lesson in lessons], total


__all__ = [
    "get_lesson",
    "update_lesson",
    "delete_lesson",
    "create_lesson",
    "list_lessons",
    "list_all_lessons",
]