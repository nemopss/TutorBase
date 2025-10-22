"""Service for managing lesson packages in the system.

This module contains business logic for working with lesson packages (LessonPackage),
including creation, updates, deletion, and metrics synchronization. Packages can be
created manually or generated from templates (LessonPackageTemplate).

Key components:
    - get_package: Retrieve a package by ID
    - list_packages: Get list of packages with filtering and pagination
    - create_package: Create a new package manually (without auto-generating lessons)
    - create_package_from_template: Create package from template with automatic lesson generation
    - update_package: Update package parameters
    - delete_package: Delete a package and all related data
    - sync_metrics: Synchronize package metrics (lesson count, progress)
    - regenerate_reminders_for_package: Regenerate all reminders for a package

Relationships with other services:
    - lesson_service: Manages lessons within packages
    - learner_service: Links packages to learners
    - template_service: Uses templates for package creation
    - package_scheduler: Generates reminders for packages
    - utils: Helper functions for lesson generation and metrics synchronization

Business logic:
    - Packages track lesson progress (total, completed, cancelled)
    - Metrics are automatically synchronized when lessons change
    - Reminders are regenerated when package schedule changes
    - All timestamps are normalized to the default timezone
    - Prometheus metrics track package creation
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from database.transaction import transactional
from database.models import LessonPackage, LessonPackageTemplate
from services.dto import LessonPackageDTO, PackageProgress
from services.exceptions import NotFoundError
from services.package_scheduler import regenerate_package_reminders
from services.utils import generate_lessons_from_template, lesson_stats, sync_package_metrics
from utils.timezone import DEFAULT_TIMEZONE, DEFAULT_TZ, normalize_to_timezone, to_utc

# Prometheus metrics
try:
    from api.prometheus_metrics import packages_created_total, db_query_duration
except ImportError:
    # Fallback if metrics not available
    packages_created_total = None
    db_query_duration = None


def _build_package_dto(package: LessonPackage) -> LessonPackageDTO:
    """Convert LessonPackage model to DTO for data transfer.

    Calculate lesson statistics (total, completed, cancelled) and build data
    transfer object with timestamps normalized to local timezone.

    Args:
        package: Lesson package model from database

    Returns:
        LessonPackageDTO with package data and calculated progress
    """
    total, completed, cancelled = lesson_stats(package.lessons or [])
    learner_name = package.learner.display_name if package.learner else None
    
    return LessonPackageDTO(
        id=package.id,
        learner_id=package.learner_id,
        learner_name=learner_name,
        template_id=package.template_id,
        title=package.title,
        status=package.status,
        start_date=normalize_to_timezone(package.start_date),
        end_date=normalize_to_timezone(package.end_date),
        timezone=DEFAULT_TIMEZONE,
        notes=package.notes,
        total_lessons=package.total_lessons,
        progress=PackageProgress(total=total, completed=completed, cancelled=cancelled),
    )


async def get_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> LessonPackageDTO:
    """Retrieve a lesson package by ID.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Lesson package ID

    Returns:
        LessonPackageDTO with package data and progress

    Raises:
        NotFoundError: If package with specified ID is not found
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    return _build_package_dto(package)


async def regenerate_reminders_for_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> None:
    """Regenerate all reminders for a lesson package.

    Delete existing reminders and create new ones based on current package
    and lesson state. Used when schedule or package parameters change.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Lesson package ID

    Raises:
        NotFoundError: If package with specified ID is not found
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    await regenerate_package_reminders(session, current_tenant, package)


async def sync_metrics(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> LessonPackageDTO:
    """Synchronize package metrics based on lesson state.

    Recalculate lesson count, statuses (completed, cancelled) and update
    total_lessons, completed_lessons, cancelled_lessons fields in package model.
    Called after lessons in the package are modified.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Lesson package ID

    Returns:
        LessonPackageDTO with updated metrics

    Raises:
        NotFoundError: If package with specified ID is not found
    """
    package, _ = await sync_package_metrics(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    return _build_package_dto(package)


async def list_packages(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
    learner_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[LessonPackageDTO], int]:
    """Get list of lesson packages with filtering and pagination.

    Supports filtering by learner, status, and text search by title.
    Returns list of packages and total count for pagination.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        limit: Maximum number of packages in result
        offset: Offset for pagination
        learner_id: Filter by learner ID (optional)
        status: Filter by package status (draft, active, completed, cancelled)
        search: Text search by package title (optional)

    Returns:
        Tuple of list of LessonPackageDTO and total package count
    """
    packages, total = await crud.fetch_lesson_packages_paginated(
        session, 
        current_tenant,
        limit=limit, 
        offset=offset,
        learner_id=learner_id,
        status=status,
        search=search,
    )
    dtos = [_build_package_dto(pkg) for pkg in packages]
    return dtos, total


@transactional(max_retries=3, backoff_factor=0.5)
async def create_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    title: str,
    notes: Optional[str] = None,
    status: str = 'draft',
    template_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    total_lessons: Optional[int] = None,
) -> LessonPackageDTO:
    """Create a new lesson package manually (without auto-generating lessons).

    Create an empty package with specified parameters. Lessons must be added
    separately via lesson_service. If template_id is specified, package will be
    linked to template, but lessons will not be created automatically (use
    create_package_from_template for that).

    After creation, reminders are automatically generated for the package and
    Prometheus metrics are updated.

    Transaction handling:
        All operations execute in a single transaction with automatic commit on success
        and rollback on error. Deadlocks are retried automatically.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner who owns the package
        title: Package title
        notes: Additional notes (optional)
        status: Package status (default 'draft')
        template_id: Template ID for linking (optional, without lesson auto-generation)
        start_date: Package start date (optional)
        total_lessons: Planned number of lessons (optional)

    Returns:
        LessonPackageDTO with created package data

    Raises:
        NotFoundError: If learner or template not found
    """
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        raise NotFoundError(f"Learner {learner_id} not found")

    template: Optional[LessonPackageTemplate] = None
    if template_id is not None:
        template = await crud.get_lesson_package_template(session, current_tenant, template_id)
        if not template:
            raise NotFoundError(f"Template {template_id} not found")

    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=template,
        title=title,
        notes=notes,
        status=status,
        start_date=to_utc(start_date, DEFAULT_TZ) if start_date else None, # TEMP: Always use DEFAULT_TZ
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=total_lessons,
    )

    session.add(package)
    await session.flush()  # Flush to get package.id for relationships
    
    await regenerate_package_reminders(session, current_tenant, package)
    
    if packages_created_total:
        packages_created_total.labels(learner_id=learner_id).inc()
    
    # Transaction will be committed by @transactional decorator
    return _build_package_dto(package)


@transactional(max_retries=3, backoff_factor=0.5)
async def create_package_from_template(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    template_id: int,
    title: str,
    notes: Optional[str],
    start_local: datetime,
    status: str = 'draft',
) -> LessonPackageDTO:
    """Create lesson package from template with automatic lesson generation.

    Create package and automatically generate all lessons according to template
    rules (lesson count, schedule, duration). After creation, synchronize package
    metrics and create reminders for all lessons.

    Business logic:
        1. Create package with parameters from template
        2. Generate lessons by template schedule (generate_lessons_from_template)
        3. Synchronize package metrics (lesson count)
        4. Create reminders for all lessons
        5. Update Prometheus metrics

    Transaction handling:
        All operations execute in a single transaction with automatic commit on success
        and rollback on error. Deadlocks are retried automatically.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner who owns the package
        template_id: Template ID for lesson generation
        title: Package title
        notes: Additional notes (optional)
        start_local: Package start date in local timezone
        status: Package status (default 'draft')

    Returns:
        LessonPackageDTO with created package data and generated lessons

    Raises:
        NotFoundError: If learner or template not found
    """
    learner = await crud.get_learner(session, current_tenant, learner_id)
    template = await crud.get_lesson_package_template(session, current_tenant, template_id)
    if not learner or not template:
        raise NotFoundError("Learner or template not found")

    if start_local.tzinfo is None:
        localized_start = start_local.replace(tzinfo=DEFAULT_TZ)
    else:
        localized_start = start_local.astimezone(DEFAULT_TZ)

    start_utc = localized_start.astimezone(timezone.utc)
    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=template,
        title=title,
        notes=notes,
        status=status,
        start_date=start_utc,
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=template.lesson_count,
    )

    session.add(package)
    await session.flush()  # Flush to get package.id for relationships
    
    await generate_lessons_from_template(session, current_tenant, package, template, localized_start)
    await sync_package_metrics(session, current_tenant, package.id)
    await regenerate_package_reminders(session, current_tenant, package)
    
    if packages_created_total:
        packages_created_total.labels(learner_id=learner_id).inc()
    
    # Transaction will be committed by @transactional decorator
    return _build_package_dto(package)


@transactional(max_retries=3, backoff_factor=0.5)
async def update_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
    *,
    title: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    total_lessons: Optional[int] = None,
) -> LessonPackageDTO:
    """Update parameters of existing lesson package.

    Update specified package fields. All parameters are optional - only passed
    values are updated. After update, package metrics are automatically synchronized.

    Note: Changing dates does not affect existing lessons. To change lesson
    schedule, use lesson_service.

    Transaction handling:
        All operations execute in a single transaction with automatic commit on success
        and rollback on error. Deadlocks are retried automatically.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Package ID to update
        title: New package title (optional)
        status: New package status (optional)
        notes: New notes (optional)
        start_date: New start date in local timezone (optional)
        end_date: New end date in local timezone (optional)
        total_lessons: New planned lesson count (optional)

    Returns:
        LessonPackageDTO with updated package data

    Raises:
        NotFoundError: If package with specified ID is not found
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")

    if title is not None:
        package.title = title
    if status is not None:
        package.status = status
    if notes is not None:
        package.notes = notes
    package.timezone = DEFAULT_TIMEZONE
    if start_date is not None:
        package.start_date = to_utc(start_date, DEFAULT_TZ)
    if end_date is not None:
        package.end_date = to_utc(end_date, DEFAULT_TZ)
    if total_lessons is not None:
        package.total_lessons = total_lessons

    session.add(package)
    await session.flush()
    await sync_package_metrics(session, current_tenant, package_id)
    
    # Transaction will be committed by @transactional decorator
    return _build_package_dto(package)


@transactional(max_retries=3, backoff_factor=0.5)
async def delete_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> None:
    """Delete lesson package and all related data.

    Delete package along with all its lessons and reminders. Operation is
    irreversible. Use with caution.

    Transaction handling:
        All operations execute in a single transaction with automatic commit on success
        and rollback on error. Deadlocks are retried automatically.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        package_id: Package ID to delete

    Raises:
        NotFoundError: If package with specified ID is not found
    """
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    await crud.delete_lesson_package(session, package)
    # Transaction will be committed by @transactional decorator


__all__ = [
    "get_package",
    "list_packages",
    "regenerate_reminders_for_package",
    "sync_metrics",
    "create_package",
    "create_package_from_template",
    "update_package",
    "delete_package",
]