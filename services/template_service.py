"""Service for managing lesson package templates.

This module contains business logic for working with lesson package templates.
Templates define reusable configurations for creating lesson packages with
predefined lesson counts, durations, and scheduling rules.

Key components:
    - get_template: Retrieve template by ID
    - list_templates: Get all templates for current tenant
    - create_template: Create new template
    - update_template: Update template parameters
    - delete_template: Delete template
    - duplicate_template: Clone existing template with modifications

Business logic:
    - Templates belong to tenants for multi-tenancy isolation
    - Templates define lesson count and duration for packages
    - default_config stores scheduling rules and other parameters
    - Templates can be duplicated for quick variations
    - Deleting template doesn't affect existing packages created from it

Relationships with other services:
    - package_service: Uses templates to create packages with auto-generated lessons
    - lesson_service: Template config influences lesson generation
    - utils: generate_lessons_from_template uses template configuration

Usage:
    Templates are used by tutors to quickly create standardized lesson packages.
    For example, a "10 Lessons Monthly" template might specify 10 lessons over
    30 days with specific scheduling rules.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import LessonPackageTemplate
from services.dto import TemplateDTO
from services.exceptions import NotFoundError
from api.dependencies import CurrentTenant


def _build_template_dto(template: LessonPackageTemplate) -> TemplateDTO:
    """Convert LessonPackageTemplate model to DTO for data transfer.

    Args:
        template: Template model from database

    Returns:
        TemplateDTO with template data
    """
    return TemplateDTO(
        id=template.id,
        name=template.name,
        description=template.description,
        lesson_count=template.lesson_count,
        duration_days=template.duration_days,
        timezone='Europe/Moscow',
        default_config=template.default_config or {},
    )


async def get_template(session: AsyncSession, current_tenant: CurrentTenant, template_id: int) -> TemplateDTO:
    """Retrieve lesson package template by ID.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        template_id: Template ID to retrieve

    Returns:
        TemplateDTO with template data

    Raises:
        NotFoundError: If template with specified ID is not found
    """
    template = await crud.get_lesson_package_template(session, current_tenant, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    return _build_template_dto(template)


async def list_templates(session: AsyncSession, current_tenant: CurrentTenant) -> list[TemplateDTO]:
    """Get all lesson package templates for current tenant.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy

    Returns:
        List of TemplateDTO for all templates belonging to tenant
    """
    templates = await crud.fetch_lesson_package_templates(session, current_tenant)
    return [_build_template_dto(tpl) for tpl in templates]


async def create_template(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    name: str,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_config: Optional[dict] = None,
) -> TemplateDTO:
    """Create a new lesson package template.

    Creates a reusable template for generating lesson packages. Template defines
    the structure and scheduling rules for packages created from it.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        name: Template name (e.g., "10 Lessons Monthly")
        description: Template description (optional)
        lesson_count: Number of lessons in packages created from template (optional)
        duration_days: Duration in days for packages (optional)
        default_config: Configuration dict for scheduling rules (optional)

    Returns:
        TemplateDTO with created template data
    """
    template = await crud.create_lesson_package_template(
        session,
        current_tenant,
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone='Europe/Moscow',
        default_config=default_config,
    )
    await session.flush()
    return _build_template_dto(template)


async def update_template(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    template_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_config: Optional[dict] = None,
) -> TemplateDTO:
    """Update lesson package template parameters.

    Updates specified template fields. All parameters are optional - only provided
    values are updated. Changes don't affect existing packages created from template.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        template_id: Template ID to update
        name: New template name (optional)
        description: New description (optional)
        lesson_count: New lesson count (optional)
        duration_days: New duration in days (optional)
        default_config: New configuration dict (optional)

    Returns:
        TemplateDTO with updated template data

    Raises:
        NotFoundError: If template with specified ID is not found
    """
    template = await crud.get_lesson_package_template(session, current_tenant, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    await crud.update_lesson_package_template(
        session,
        template,
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone='Europe/Moscow',
        default_config=default_config,
    )
    await session.flush([template])
    return _build_template_dto(template)


async def delete_template(session: AsyncSession, current_tenant: CurrentTenant, template_id: int) -> None:
    """Delete lesson package template.

    Deletes template. Existing packages created from this template are not affected.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        template_id: Template ID to delete

    Raises:
        NotFoundError: If template with specified ID is not found
    """
    template = await crud.get_lesson_package_template(session, current_tenant, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    await crud.delete_lesson_package_template(session, template)


async def duplicate_template(session: AsyncSession, current_tenant: CurrentTenant, template_id: int, *, name: Optional[str] = None) -> TemplateDTO:
    """Duplicate existing template with optional name change.

    Creates a copy of existing template with all its configuration. Useful for
    creating variations of templates without starting from scratch.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        template_id: Template ID to duplicate
        name: Name for duplicated template (optional, defaults to "Original Name (копия)")

    Returns:
        TemplateDTO with duplicated template data

    Raises:
        NotFoundError: If template with specified ID is not found
    """
    template = await crud.get_lesson_package_template(session, current_tenant, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    new_name = name or f"{template.name} (копия)"
    clone = await crud.create_lesson_package_template(
        session,
        current_tenant,
        name=new_name,
        description=template.description,
        lesson_count=template.lesson_count,
        duration_days=template.duration_days,
        default_timezone='Europe/Moscow',
        default_config=template.default_config,
    )
    await session.flush()
    return _build_template_dto(clone)


__all__ = [
    "get_template",
    "list_templates",
    "create_template",
    "update_template",
    "delete_template",
    "duplicate_template",
]