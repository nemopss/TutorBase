from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, admin_or_teacher_required, get_current_tenant, get_session
from api.schemas.billing import BillingPlanResponse, BillingSnapshotResponse
from services import billing_service

router = APIRouter()


def _snapshot_response(snapshot: billing_service.BillingSnapshot | None) -> BillingSnapshotResponse:
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required for billing",
        )
    return BillingSnapshotResponse(**snapshot.__dict__)


@router.get("/current", response_model=BillingSnapshotResponse)
async def get_current_billing(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> BillingSnapshotResponse:
    snapshot = await billing_service.get_billing_snapshot(session, current_tenant)
    return _snapshot_response(snapshot)


@router.get("/plans", response_model=list[BillingPlanResponse])
async def list_billing_plans(
    session: AsyncSession = Depends(get_session),
) -> list[BillingPlanResponse]:
    plans = await billing_service.list_public_plans(session)
    return [
        BillingPlanResponse(
            code=plan.code,
            name=plan.name,
            active_learners_limit=plan.active_learners_limit,
            monthly_price_rub=plan.monthly_price_rub,
            yearly_price_rub=plan.yearly_price_rub,
            is_public=plan.is_public,
            display_order=plan.display_order,
        )
        for plan in plans
    ]
