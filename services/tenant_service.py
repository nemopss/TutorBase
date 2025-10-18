from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import Tenant
from services.exceptions import NotFoundError


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    contact_email: Optional[str] = None,
    is_active: bool = True,
) -> Tenant:
    return await crud.create_tenant(
        session,
        name=name,
        slug=slug,
        contact_email=contact_email,
        is_active=is_active,
    )


async def get_tenant(session: AsyncSession, tenant_id: int) -> Tenant:
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return tenant


async def list_tenants(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Tenant], int]:
    return await crud.list_tenants(session, limit=limit, offset=offset)


async def update_tenant(
    session: AsyncSession,
    tenant_id: int,
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    contact_email: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Tenant:
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return await crud.update_tenant(
        session,
        tenant,
        name=name,
        slug=slug,
        contact_email=contact_email,
        is_active=is_active,
    )


async def delete_tenant(session: AsyncSession, tenant_id: int) -> None:
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    await crud.delete_tenant(session, tenant)
