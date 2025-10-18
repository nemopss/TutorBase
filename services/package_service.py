from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
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
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    return _build_package_dto(package)


async def regenerate_reminders_for_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> None:
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    await regenerate_package_reminders(session, package)


async def sync_metrics(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> LessonPackageDTO:
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

    await session.flush([package])
    await regenerate_package_reminders(session, current_tenant, package)    
    await session.flush([package])
    
    if packages_created_total:
        packages_created_total.labels(learner_id=learner_id).inc()
    
    return _build_package_dto(package)


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

    await session.flush([package])
    await generate_lessons_from_template(session, current_tenant, package, template, localized_start)
    await sync_package_metrics(session, current_tenant, package.id)
    await regenerate_package_reminders(session, current_tenant, package)
    
    if packages_created_total:
        packages_created_total.labels(learner_id=learner_id).inc()
    
    return _build_package_dto(package)


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

    await session.flush([package])
    await sync_package_metrics(session, current_tenant, package_id)
    return _build_package_dto(package)


async def delete_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> None:
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        raise NotFoundError(f"Package {package_id} not found")
    await crud.delete_lesson_package(session, package)


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