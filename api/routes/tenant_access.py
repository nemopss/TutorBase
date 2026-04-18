from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import CurrentTenant, get_current_tenant_with_access_override
from api.schemas import TenantAccessResponse
from services import tenant_access_service

router = APIRouter()


@router.get("/current", response_model=TenantAccessResponse)
async def get_current_tenant_access(
    current_tenant: CurrentTenant = Depends(get_current_tenant_with_access_override),
) -> TenantAccessResponse:
    if current_tenant.tenant_id is None:
        return TenantAccessResponse(
            tenant_id=None,
            status="global",
            mode=tenant_access_service.ACCESS_MODE_FULL,
            access_until=None,
            grace_until=None,
            is_lifetime=True,
            reason="platform_global_context",
            notes=None,
            bypass_access_restrictions=True,
        )

    return TenantAccessResponse(
        tenant_id=current_tenant.tenant_id,
        status=current_tenant.access_status or tenant_access_service.ACCESS_STATUS_LIFETIME,
        mode=current_tenant.access_mode or tenant_access_service.ACCESS_MODE_FULL,
        access_until=current_tenant.access_until,
        grace_until=current_tenant.grace_until,
        is_lifetime=current_tenant.access_status == tenant_access_service.ACCESS_STATUS_LIFETIME,
        reason=current_tenant.access_reason,
        notes=None,
        bypass_access_restrictions=current_tenant.bypass_access_restrictions,
    )
