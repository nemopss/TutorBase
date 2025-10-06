from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, admin_required
from api.schemas import (
    TemplateCreateRequest,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdateRequest,
)
from services import template_service
from services.dto import TemplateDTO
from services.exceptions import NotFoundError

router = APIRouter()


def _to_response(dto: TemplateDTO) -> TemplateResponse:
    return TemplateResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        lesson_count=dto.lesson_count,
        duration_days=dto.duration_days,
        timezone=dto.timezone,
        default_config=dto.default_config or {},
    )


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    session: AsyncSession = Depends(get_session),
) -> TemplateListResponse:
    templates = await template_service.list_templates(session)
    return TemplateListResponse(total=len(templates), items=[_to_response(tpl) for tpl in templates])


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
) -> TemplateResponse:
    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)


@router.post("/create", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_endpoint(
    payload: TemplateCreateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    template = await template_service.create_template(
        session,
        name=payload.name,
        description=payload.description,
        lesson_count=payload.lesson_count,
        duration_days=payload.duration_days,
        default_timezone=payload.timezone,
        default_config=payload.default_config,
    )
    await session.commit()
    return _to_response(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template_endpoint(
    template_id: int,
    payload: TemplateUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    try:
        template = await template_service.update_template(
            session,
            template_id,
            name=payload.name,
            description=payload.description,
            lesson_count=payload.lesson_count,
            duration_days=payload.duration_days,
            default_timezone=payload.timezone,
            default_config=payload.default_config,
        )
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)


@router.delete("/{template_id}")
async def delete_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_required),
):
    try:
        await template_service.delete_template(session, template_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    try:
        template = await template_service.duplicate_template(session, template_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)
