from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import admin_required, get_current_user, get_session
from api.schemas import (
    PaginatedResponse,
    PaginationParams,
    PlatformTenantResponse,
    TenantAccessActionRequest,
    TenantAccessGrantRequest,
    TenantAccessResponse,
)
from database.models import Tenant, TenantAccess, User
from services import tenant_access_service
from services.exceptions import NotFoundError

router = APIRouter()


def _access_response(
    access: TenantAccess | None,
    *,
    tenant_id: int,
) -> TenantAccessResponse:
    snapshot = tenant_access_service.evaluate_access(access, tenant_id)
    return TenantAccessResponse(
        tenant_id=tenant_id,
        status=snapshot.status,
        mode=snapshot.mode,
        access_until=snapshot.access_until,
        grace_until=snapshot.grace_until,
        is_lifetime=snapshot.is_lifetime,
        reason=snapshot.reason,
        notes=access.notes if access else None,
        bypass_access_restrictions=False,
    )


def _tenant_response(tenant: Tenant, access: TenantAccess | None) -> PlatformTenantResponse:
    return PlatformTenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        contact_email=tenant.contact_email,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        access=_access_response(access, tenant_id=tenant.id),
    )


@router.get("/tenants", response_model=PaginatedResponse[PlatformTenantResponse])
async def list_platform_tenants(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PaginatedResponse[PlatformTenantResponse]:
    total_result = await session.execute(select(func.count()).select_from(Tenant))
    total = total_result.scalar_one()

    tenants_result = await session.execute(
        select(Tenant)
        .order_by(Tenant.id)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    tenants = list(tenants_result.scalars().all())
    tenant_ids = [tenant.id for tenant in tenants]

    access_by_tenant_id: dict[int, TenantAccess] = {}
    if tenant_ids:
        access_result = await session.execute(
            select(TenantAccess).where(TenantAccess.tenant_id.in_(tenant_ids))
        )
        access_by_tenant_id = {
            access.tenant_id: access for access in access_result.scalars().all()
        }

    items = [
        _tenant_response(tenant, access_by_tenant_id.get(tenant.id))
        for tenant in tenants
    ]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.post("/tenants/{tenant_id}/access/grant", response_model=TenantAccessResponse)
async def grant_tenant_access(
    tenant_id: int,
    payload: TenantAccessGrantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.grant_access(
            session,
            tenant_id,
            days=payload.days,
            actor_user_id=current_user.id,
            notes=payload.notes,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/lifetime", response_model=TenantAccessResponse)
async def grant_tenant_lifetime_access(
    tenant_id: int,
    payload: TenantAccessActionRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.grant_lifetime_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            notes=payload.notes if payload else None,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/suspend", response_model=TenantAccessResponse)
async def suspend_tenant_access(
    tenant_id: int,
    payload: TenantAccessActionRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.suspend_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            notes=payload.notes if payload else None,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/resume", response_model=TenantAccessResponse)
async def resume_tenant_access(
    tenant_id: int,
    payload: TenantAccessGrantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.resume_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            days=payload.days,
            notes=payload.notes,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)
