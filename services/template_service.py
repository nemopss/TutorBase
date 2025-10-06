from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import LessonPackageTemplate
from services.dto import TemplateDTO
from services.exceptions import NotFoundError


def _build_template_dto(template: LessonPackageTemplate) -> TemplateDTO:
    return TemplateDTO(
        id=template.id,
        name=template.name,
        description=template.description,
        lesson_count=template.lesson_count,
        duration_days=template.duration_days,
        timezone=template.default_timezone or 'Europe/Moscow',
        default_config=template.default_config or {},
    )


async def get_template(session: AsyncSession, template_id: int) -> TemplateDTO:
    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    return _build_template_dto(template)


async def list_templates(session: AsyncSession) -> list[TemplateDTO]:
    templates = await crud.fetch_lesson_package_templates(session)
    return [_build_template_dto(tpl) for tpl in templates]


async def create_template(
    session: AsyncSession,
    *,
    name: str,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_timezone: str = 'Europe/Moscow',
    default_config: Optional[dict] = None,
) -> TemplateDTO:
    template = await crud.create_lesson_package_template(
        session,
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone=default_timezone,
        default_config=default_config,
    )
    return _build_template_dto(template)


async def update_template(
    session: AsyncSession,
    template_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_timezone: Optional[str] = None,
    default_config: Optional[dict] = None,
) -> TemplateDTO:
    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    await crud.update_lesson_package_template(
        session,
        template,
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone=default_timezone,
        default_config=default_config,
    )
    await session.flush([template])
    return _build_template_dto(template)


async def delete_template(session: AsyncSession, template_id: int) -> None:
    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    await crud.delete_lesson_package_template(session, template)


async def duplicate_template(session: AsyncSession, template_id: int, *, name: Optional[str] = None) -> TemplateDTO:
    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
        raise NotFoundError(f"Template {template_id} not found")
    new_name = name or f"{template.name} (копия)"
    clone = await crud.create_lesson_package_template(
        session,
        name=new_name,
        description=template.description,
        lesson_count=template.lesson_count,
        duration_days=template.duration_days,
        default_timezone=template.default_timezone,
        default_config=template.default_config,
    )
    return _build_template_dto(clone)


__all__ = [
    "get_template",
    "list_templates",
    "create_template",
    "update_template",
    "delete_template",
    "duplicate_template",
]
