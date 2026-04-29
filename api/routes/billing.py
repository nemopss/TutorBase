from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, admin_or_teacher_required, get_current_tenant, get_session
from api.schemas.billing import (
    BillingCheckoutRequest,
    BillingCheckoutPreviewResponse,
    BillingCheckoutResponse,
    BillingPlanResponse,
    BillingSnapshotResponse,
    YooKassaWebhookPayload,
)
from services import billing_service, yookassa_service
from services.exceptions import NotFoundError, ServiceError, ValidationError

router = APIRouter()


def _checkout_preview_response(quote: yookassa_service.CheckoutQuote) -> BillingCheckoutPreviewResponse:
    return BillingCheckoutPreviewResponse(
        plan_code=quote.plan_code,
        plan_name=quote.plan_name,
        billing_period=quote.billing_period,
        billing_action=quote.billing_action,
        amount_due=yookassa_service._amount_value(quote.amount_due),
        full_amount=yookassa_service._amount_value(quote.full_amount),
        credit_amount=yookassa_service._amount_value(quote.credit_amount),
        current_plan_code=quote.current_plan_code,
        current_plan_name=quote.current_plan_name,
        resulting_period_start=quote.resulting_period_start,
        resulting_period_end=quote.resulting_period_end,
        message=quote.message,
    )


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


@router.post("/checkout/preview", response_model=BillingCheckoutPreviewResponse)
async def preview_billing_checkout(
    payload: BillingCheckoutRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> BillingCheckoutPreviewResponse:
    try:
        quote = await yookassa_service.create_checkout_quote(
            session,
            current_tenant,
            plan_code=payload.plan_code,
            billing_period=payload.billing_period,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return _checkout_preview_response(quote)


@router.post("/checkout", response_model=BillingCheckoutResponse)
async def create_billing_checkout(
    payload: BillingCheckoutRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> BillingCheckoutResponse:
    try:
        payment = await yookassa_service.create_checkout_payment(
            session,
            current_tenant,
            plan_code=payload.plan_code,
            billing_period=payload.billing_period,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return BillingCheckoutResponse(
        payment_id=payment.payment_id,
        status=payment.status,
        confirmation_url=payment.confirmation_url,
        amount_due=payment.amount_due,
        billing_action=payment.billing_action,
    )


@router.post("/yookassa/webhook")
async def receive_yookassa_webhook(
    payload: YooKassaWebhookPayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    try:
        await yookassa_service.process_webhook(session, payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"ok": True}
