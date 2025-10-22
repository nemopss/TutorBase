from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_required, get_current_tenant, CurrentTenant
from api.schemas import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    PaginationParams,
    PaginatedResponse,
)
from services import tenant_service
from services.exceptions import NotFoundError

router = APIRouter()


def _to_response(tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        contact_email=tenant.contact_email,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantResponse:
    if not current_tenant.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super-admins can create tenants")
    
    tenant = await tenant_service.create_tenant(
        session,
        name=payload.name,
        slug=payload.slug,
        contact_email=payload.contact_email,
        is_active=payload.is_active,
    )
    await session.commit()
    return _to_response(tenant)


@router.get("", response_model=PaginatedResponse[TenantResponse])
async def list_tenants(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> PaginatedResponse[TenantResponse]:
    if not current_tenant.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super-admins can list tenants")

    tenants, total = await tenant_service.list_tenants(
        session,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    items = [_to_response(t) for t in tenants]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantResponse:
    if not current_tenant.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super-admins can view tenants")

    try:
        tenant = await tenant_service.get_tenant(session, tenant_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantResponse:
    if not current_tenant.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super-admins can update tenants")

    try:
        tenant = await tenant_service.update_tenant(
            session,
            tenant_id,
            name=payload.name,
            slug=payload.slug,
            contact_email=payload.contact_email,
            is_active=payload.is_active,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
):
    if not current_tenant.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super-admins can delete tenants")

    try:
        await tenant_service.delete_tenant(session, tenant_id)
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
