from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, get_current_tenant, CurrentTenant
from api.schemas import (
    TemplateListResponse,
    TemplateResponse,
    TemplateCreateRequest,
    TemplateUpdateRequest,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from services import template_service
from services.dto import TemplateDTO
from services.exceptions import NotFoundError

router = APIRouter()


def _to_response(dto: TemplateDTO | dict) -> TemplateResponse:
    """Convert TemplateDTO or dict (from cache) to TemplateResponse.
    
    Args:
        dto: TemplateDTO object or dict from cache
        
    Returns:
        TemplateResponse for API response
    """
    if isinstance(dto, dict):
        # Cache returned dict, convert directly
        return TemplateResponse(**dto)
    
    # TemplateDTO object
    return TemplateResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        lesson_count=dto.lesson_count,
        duration_days=dto.duration_days,
        default_config=dto.default_config,
        timezone=dto.timezone,
    )


@router.get("", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> PaginatedResponse[TemplateResponse]:
    templates = await template_service.list_templates(session, current_tenant)
    
    # Apply pagination manually since service doesn't support it yet
    total = len(templates)
    paginated_templates = templates[pagination.offset:pagination.offset + pagination.limit]
    
    # Convert to response objects (handles both DTO and dict from cache)
    items = [_to_response(tpl) for tpl in paginated_templates]
    
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> TemplateResponse:
    try:
        template = await template_service.get_template(session, current_tenant, template_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)


@router.post("/create", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_endpoint(
    payload: TemplateCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    template = await template_service.create_template(
        session,
        current_tenant,
        name=payload.name,
        description=payload.description,
        lesson_count=payload.lesson_count,
        duration_days=payload.duration_days,
        default_config=payload.default_config,
    )
    return _to_response(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template_endpoint(
    template_id: int,
    payload: TemplateUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    try:
        template = await template_service.update_template(
            session,
            current_tenant,
            template_id,
            name=payload.name,
            description=payload.description,
            lesson_count=payload.lesson_count,
            duration_days=payload.duration_days,
            default_config=payload.default_config,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)


@router.delete("/{template_id}")
async def delete_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
):
    try:
        await template_service.delete_template(session, current_tenant, template_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_template_endpoint(
    template_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> TemplateResponse:
    try:
        template = await template_service.duplicate_template(session, current_tenant, template_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(template)