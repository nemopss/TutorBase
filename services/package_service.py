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
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from database.transaction import transactional
from database.models import Lesson, LessonPackage, LessonPackageTemplate, Payment
from notifications.domain.enums import EventType
from services.dto import LessonPackageDTO, PackageBalance, PackageProgress
from services.exceptions import NotFoundError
from services.notification_reconciliation import enqueue_notification_event_reconciliation
# Removed: from services.package_scheduler import regenerate_package_reminders (circular import)
# Using lazy import inside functions instead
from services.utils import generate_lessons_from_template, lesson_stats, sync_package_metrics
from services.finance_service import calculate_package_price
from utils.timezone import DEFAULT_TIMEZONE, DEFAULT_TZ, normalize_to_timezone, to_utc

# Prometheus metrics
try:
    from api.prometheus_metrics import packages_created_total, db_query_duration
except ImportError:
    # Fallback if metrics not available
    packages_created_total = None
    db_query_duration = None


PACKAGE_TYPE_PACKAGE = "package"
PACKAGE_TYPE_ONE_OFF = "one_off"
PACKAGE_TYPE_ALL = "all"
VALID_PACKAGE_TYPES = {PACKAGE_TYPE_PACKAGE, PACKAGE_TYPE_ONE_OFF}
SCHEDULE_MODE_FIXED = "fixed"
SCHEDULE_MODE_FLEXIBLE = "flexible"
SCHEDULE_MODE_ONE_OFF = "one_off"
VALID_SCHEDULE_MODES = {
    SCHEDULE_MODE_FIXED,
    SCHEDULE_MODE_FLEXIBLE,
    SCHEDULE_MODE_ONE_OFF,
}


async def _enqueue_lesson_reconciliation_for_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
    *,
    reason: str,
) -> None:
    result = await session.execute(
        select(Lesson.id)
        .where(Lesson.package_id == package_id)
        .order_by(Lesson.scheduled_at, Lesson.id)
    )
    for lesson_id in result.scalars():
        await enqueue_notification_event_reconciliation(
            session,
            current_tenant,
            event_type=EventType.LESSON,
            event_id=lesson_id,
            reason=reason,
        )
    await enqueue_notification_event_reconciliation(
        session,
        current_tenant,
        event_type=EventType.PACKAGE,
        event_id=package_id,
        reason=reason,
    )


def _get_next_lesson_date(lessons: list) -> Optional[datetime]:
    """Get the date of the next scheduled lesson.
    
    Finds the earliest lesson with status 'scheduled' or 'rescheduled'.
    
    Args:
        lessons: List of Lesson models
        
    Returns:
        Datetime of next lesson or None if no upcoming lessons
    """
    upcoming = [
        lesson for lesson in (lessons or [])
        if lesson.status in ('scheduled', 'rescheduled')
    ]
    if not upcoming:
        return None
    # Sort by scheduled_at and return the earliest
    upcoming.sort(key=lambda x: x.scheduled_at)
    return normalize_to_timezone(upcoming[0].scheduled_at)


def _build_package_dto(package: LessonPackage, total_paid: float = 0.0) -> LessonPackageDTO:
    """Convert LessonPackage model to DTO for data transfer.

    Calculate lesson statistics (total, completed, cancelled) and build data
    transfer object with timestamps normalized to local timezone.

    Args:
        package: Lesson package model from database
        total_paid: Total amount paid for this package (default 0.0)

    Returns:
        LessonPackageDTO with package data and calculated progress
    """
    total, completed, cancelled = lesson_stats(package.lessons or [])
    scheduled = sum(
        1
        for lesson in (package.lessons or [])
        if lesson.status in ("scheduled", "rescheduled")
    )
    purchased = package.total_lessons if package.total_lessons is not None else total
    purchased = max(int(purchased or 0), 0)
    price = float(package.price or 0)
    paid = max(float(total_paid or 0), 0)
    learner_name = package.learner.display_name if package.learner else None
    next_lesson = _get_next_lesson_date(package.lessons)
    
    return LessonPackageDTO(
        id=package.id,
        learner_id=package.learner_id,
        learner_name=learner_name,
        template_id=package.template_id,
        package_type=package.package_type or PACKAGE_TYPE_PACKAGE,
        schedule_mode=package.schedule_mode or (
            SCHEDULE_MODE_ONE_OFF
            if package.package_type == PACKAGE_TYPE_ONE_OFF
            else SCHEDULE_MODE_FLEXIBLE
        ),
        renewal_enabled=bool(package.renewal_enabled),
        title=package.title,
        status=package.status,
        start_date=normalize_to_timezone(package.start_date),
        end_date=normalize_to_timezone(package.end_date),
        timezone=DEFAULT_TIMEZONE,
        notes=package.notes,
        total_lessons=package.total_lessons,
        progress=PackageProgress(total=total, completed=completed, cancelled=cancelled),
        price=float(package.price) if package.price else None,
        payment_status=package.payment_status or 'unpaid',
        total_paid=paid,
        next_lesson_date=next_lesson,
        balance=PackageBalance(
            purchased=purchased,
            completed=completed,
            scheduled=scheduled,
            cancelled=cancelled,
            remaining=max(purchased - completed, 0),
            available_to_schedule=max(purchased - completed - scheduled, 0),
            amount_total=price,
            amount_paid=paid,
            amount_due=max(price - paid, 0),
        ),
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
    from decimal import Decimal
    from sqlalchemy import func, select
    from database.models import Payment
    
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    
    # Get total paid for this package
    result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.package_id == package_id,
            Payment.voided_at.is_(None),
        )
    )
    total_paid = float(result.scalar() or 0)
    
    return _build_package_dto(package, total_paid=total_paid)


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
    # Lazy import to avoid circular dependency
    from services.package_scheduler import regenerate_package_reminders
    
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
    package_type: Optional[str] = PACKAGE_TYPE_PACKAGE,
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
        package_type: Package type filter. Use "all" or None to include all types.

    Returns:
        Tuple of list of LessonPackageDTO and total package count
    """
    package_type_filter = None if package_type in (None, PACKAGE_TYPE_ALL) else package_type
    if package_type_filter is not None and package_type_filter not in VALID_PACKAGE_TYPES:
        from services.exceptions import ValidationError

        raise ValidationError("Invalid package_type")

    packages, total = await crud.fetch_lesson_packages_paginated(
        session, 
        current_tenant,
        limit=limit, 
        offset=offset,
        learner_id=learner_id,
        status=status,
        search=search,
        package_type=package_type_filter,
    )
    paid_by_package: dict[int, float] = {}
    package_ids = [package.id for package in packages]
    if package_ids:
        payment_result = await session.execute(
            select(
                Payment.package_id,
                func.coalesce(func.sum(Payment.amount), Decimal("0")),
            )
            .where(
                Payment.tenant_id == current_tenant.tenant_id,
                Payment.package_id.in_(package_ids),
                Payment.voided_at.is_(None),
            )
            .group_by(Payment.package_id)
        )
        paid_by_package = {
            package_id: float(total_paid or 0)
            for package_id, total_paid in payment_result.all()
        }
    dtos = [
        _build_package_dto(pkg, total_paid=paid_by_package.get(pkg.id, 0.0))
        for pkg in packages
    ]
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
    schedule_mode: str = SCHEDULE_MODE_FLEXIBLE,
    renewal_enabled: bool = False,
    price: Optional[Decimal] = None,
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

    if schedule_mode != SCHEDULE_MODE_FLEXIBLE:
        from services.exceptions import ValidationError

        raise ValidationError("Manual packages must use flexible schedule mode")
    if renewal_enabled:
        from services.exceptions import ValidationError

        raise ValidationError("Renewal notifications require a fixed package")

    resolved_price = price if price is not None else calculate_package_price(learner.lesson_rate, total_lessons)
    
    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=template,
        schedule_mode=schedule_mode,
        renewal_enabled=False,
        title=title,
        notes=notes,
        status=status,
        start_date=to_utc(start_date, DEFAULT_TZ) if start_date else None, # TEMP: Always use DEFAULT_TZ
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=total_lessons,
    )
    
    # Set financial fields
    package.price = resolved_price
    package.payment_status = 'unpaid'

    session.add(package)
    await session.flush()  # Flush to get package.id for relationships
    
    # Lazy import to avoid circular dependency
    from services.package_scheduler import regenerate_package_reminders
    await regenerate_package_reminders(session, current_tenant, package)
    await enqueue_notification_event_reconciliation(
        session,
        current_tenant,
        event_type=EventType.PACKAGE,
        event_id=package.id,
        reason="package_created",
    )
    
    if packages_created_total:
        packages_created_total.inc()
    
    # Transaction will be committed by @transactional decorator
    return _build_package_dto(package)


@transactional(max_retries=3, backoff_factor=0.5)
async def create_one_off_lesson(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    scheduled_at: datetime,
    duration_minutes: int = 60,
    title: Optional[str] = None,
    price: Optional[Decimal] = None,
    notes: Optional[str] = None,
) -> LessonPackageDTO:
    """Create a package-backed one-off lesson.

    One-off lessons are stored as a dedicated package type with exactly one
    lesson. This keeps finance, reminders, and lesson lists on the existing
    package path while allowing regular package views to hide them by default.
    """
    from services.package_scheduler import regenerate_package_reminders

    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        raise NotFoundError(f"Learner {learner_id} not found")

    lesson_utc = to_utc(scheduled_at, DEFAULT_TZ)
    lesson_price = price if price is not None else learner.lesson_rate

    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=None,
        package_type=PACKAGE_TYPE_ONE_OFF,
        schedule_mode=SCHEDULE_MODE_ONE_OFF,
        renewal_enabled=False,
        title=title or "Разовый урок",
        notes=notes,
        status="active",
        start_date=lesson_utc,
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=1,
    )
    package.price = lesson_price
    package.payment_status = "unpaid"
    session.add(package)
    await session.flush()

    await crud.create_lesson(
        session,
        current_tenant,
        package,
        scheduled_at=lesson_utc,
        duration_minutes=duration_minutes,
        status="scheduled",
        sequence_index=1,
    )
    await session.flush()
    await sync_package_metrics(session, current_tenant, package.id)
    await regenerate_package_reminders(session, current_tenant, package)
    await _enqueue_lesson_reconciliation_for_package(
        session,
        current_tenant,
        package.id,
        reason="package_lessons_created",
    )

    if packages_created_total:
        packages_created_total.inc()

    return _build_package_dto(package)


@transactional(max_retries=3, backoff_factor=0.5)
async def create_package_with_schedule(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    title: str,
    notes: Optional[str] = None,
    status: str = 'draft',
    lesson_dates: list[dict],  # [{"datetime": "...", "duration": 60}, ...]
    renewal_enabled: bool = False,
    price: Optional[Decimal] = None,
) -> LessonPackageDTO:
    """Create lesson package with lessons from schedule preview.

    Create package and lessons based on dates generated from learner's schedule.
    Used when creating packages with schedule-based lesson generation.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner who owns the package
        title: Package title
        notes: Additional notes (optional)
        status: Package status (default 'draft')
        lesson_dates: List of lesson dates with datetime and duration

    Returns:
        LessonPackageDTO with created package data

    Raises:
        NotFoundError: If learner not found
        ValidationError: If no lesson dates provided
    """
    from services.exceptions import ValidationError
    from database.models import Lesson
    from dateutil import parser as date_parser
    
    if not lesson_dates:
        raise ValidationError("At least one lesson date is required")
    
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        raise NotFoundError(f"Learner {learner_id} not found")

    total_lessons = len(lesson_dates)
    
    resolved_price = price if price is not None else calculate_package_price(learner.lesson_rate, total_lessons)
    
    parsed_lesson_dates = [
        date_parser.isoparse(lesson_data["datetime"])
        for lesson_data in lesson_dates
    ]
    lesson_dates_utc = [
        lesson_dt.astimezone(timezone.utc)
        if lesson_dt.tzinfo
        else lesson_dt.replace(tzinfo=timezone.utc)
        for lesson_dt in parsed_lesson_dates
    ]
    start_utc = min(lesson_dates_utc)
    end_utc = max(lesson_dates_utc)
    
    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=None,
        schedule_mode=SCHEDULE_MODE_FIXED,
        renewal_enabled=renewal_enabled,
        title=title,
        notes=notes,
        status=status,
        start_date=start_utc,
        end_date=end_utc,
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=total_lessons,
    )
    
    # Set financial fields
    package.price = resolved_price
    package.payment_status = 'unpaid'

    session.add(package)
    await session.flush()  # Flush to get package.id
    
    # Create lessons from dates
    for idx, (lesson_data, lesson_utc) in enumerate(zip(lesson_dates, lesson_dates_utc)):
        lesson = Lesson(
            tenant_id=current_tenant.tenant_id,
            package_id=package.id,
            scheduled_at=lesson_utc,
            duration_minutes=lesson_data.get("duration", 60),
            status="scheduled",
            sequence_index=idx + 1,
        )
        session.add(lesson)
    
    await session.flush()
    await sync_package_metrics(session, current_tenant, package.id)
    
    # Lazy import to avoid circular dependency
    from services.package_scheduler import regenerate_package_reminders
    await regenerate_package_reminders(session, current_tenant, package)
    await _enqueue_lesson_reconciliation_for_package(
        session,
        current_tenant,
        package.id,
        reason="package_lessons_created",
    )
    
    if packages_created_total:
        packages_created_total.inc()
    
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
    renewal_enabled: bool = False,
    price: Optional[Decimal] = None,
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
    
    resolved_price = price if price is not None else calculate_package_price(learner.lesson_rate, template.lesson_count)
    
    package = await crud.create_lesson_package(
        session,
        current_tenant,
        learner=learner,
        template=template,
        schedule_mode=SCHEDULE_MODE_FIXED,
        renewal_enabled=renewal_enabled,
        title=title,
        notes=notes,
        status=status,
        start_date=start_utc,
        timezone_name=DEFAULT_TIMEZONE,
        total_lessons=template.lesson_count,
    )
    
    # Set financial fields
    package.price = resolved_price
    package.payment_status = 'unpaid'

    session.add(package)
    await session.flush()  # Flush to get package.id for relationships
    
    await generate_lessons_from_template(session, current_tenant, package, template, localized_start)
    package, lessons = await sync_package_metrics(session, current_tenant, package.id)
    if package is None:
        raise NotFoundError("Created package disappeared during metric synchronization")
    if lessons:
        package.end_date = lessons[-1].scheduled_at
        await session.flush([package])
    
    # Lazy import to avoid circular dependency
    from services.package_scheduler import regenerate_package_reminders
    await regenerate_package_reminders(session, current_tenant, package)
    await _enqueue_lesson_reconciliation_for_package(
        session,
        current_tenant,
        package.id,
        reason="package_lessons_created",
    )
    
    if packages_created_total:
        packages_created_total.inc()
    
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
    schedule_mode: Optional[str] = None,
    renewal_enabled: Optional[bool] = None,
    price: Optional[Decimal] = None,
    start_date_set: bool = False,
    end_date_set: bool = False,
    price_set: bool = False,
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
    if schedule_mode is not None:
        if package.package_type == PACKAGE_TYPE_ONE_OFF and schedule_mode != SCHEDULE_MODE_ONE_OFF:
            from services.exceptions import ValidationError

            raise ValidationError("One-off lessons cannot be converted to packages")
        if schedule_mode not in VALID_SCHEDULE_MODES:
            from services.exceptions import ValidationError

            raise ValidationError("Invalid schedule mode")
        package.schedule_mode = schedule_mode
        if schedule_mode != SCHEDULE_MODE_FIXED:
            package.renewal_enabled = False
            package.end_date = None
    if renewal_enabled is not None:
        if renewal_enabled and package.schedule_mode != SCHEDULE_MODE_FIXED:
            from services.exceptions import ValidationError

            raise ValidationError("Renewal notifications require a fixed package")
        package.renewal_enabled = renewal_enabled
    package.timezone = DEFAULT_TIMEZONE
    effective_start_date_set = start_date_set or start_date is not None
    effective_end_date_set = end_date_set or end_date is not None
    if effective_start_date_set:
        package.start_date = to_utc(start_date, DEFAULT_TZ) if start_date is not None else None
    if effective_end_date_set:
        package.end_date = to_utc(end_date, DEFAULT_TZ) if end_date is not None else None
    
    # Recalculate price if total_lessons changed and price wasn't manually set
    if total_lessons is not None and total_lessons != package.total_lessons:
        package.total_lessons = total_lessons
        # Only recalculate if price was auto-calculated (not manually set)
        # We recalculate if learner has a rate
        learner = await crud.get_learner(session, current_tenant, package.learner_id)
        if learner and learner.lesson_rate:
            new_price = calculate_package_price(learner.lesson_rate, total_lessons)
            package.price = new_price
    elif total_lessons is not None:
        package.total_lessons = total_lessons
    if price_set:
        package.price = price

    session.add(package)
    await session.flush()
    package, _ = await sync_package_metrics(session, current_tenant, package_id)
    if package is None:
        raise NotFoundError(f"Package {package_id} not found")
    if any(
        value is not None
        for value in (title, status, total_lessons, schedule_mode, renewal_enabled)
    ) or effective_start_date_set or effective_end_date_set or price_set:
        from services.package_scheduler import regenerate_package_reminders

        await regenerate_package_reminders(session, current_tenant, package)
    if (
        any(value is not None for value in (title, status, schedule_mode, renewal_enabled))
        or effective_end_date_set
    ):
        await enqueue_notification_event_reconciliation(
            session,
            current_tenant,
            event_type=EventType.PACKAGE,
            event_id=package.id,
            reason="package_updated",
        )
    
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
    "create_package_with_schedule",
    "create_package_from_template",
    "update_package",
    "delete_package",
]
