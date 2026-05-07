from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, admin_or_teacher_required, get_current_tenant, get_session
from api.schemas.analytics import AnalyticsOverviewResponse
from services.analytics_service import build_analytics_overview

router = APIRouter()


def _require_tenant_context(current_tenant: CurrentTenant) -> None:
    if current_tenant.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required for analytics endpoints",
        )


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def analytics_overview(
    from_date: datetime = Query(..., description="Analytics period start"),
    to_date: datetime = Query(..., description="Analytics period end"),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> AnalyticsOverviewResponse:
    _require_tenant_context(current_tenant)

    start = from_date if from_date.tzinfo else from_date.replace(tzinfo=timezone.utc)
    end = to_date if to_date.tzinfo else to_date.replace(tzinfo=timezone.utc)
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be before to_date",
        )

    return await build_analytics_overview(
        session,
        current_tenant,
        from_date=start,
        to_date=end,
    )
