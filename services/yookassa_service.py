from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from config import config
from database.models import BillingEvent, Tenant
from services import billing_service
from services.exceptions import ServiceError, ValidationError


class YooKassaError(ServiceError):
    """Raised when YooKassa cannot process a billing request."""


@dataclass(frozen=True)
class CheckoutPayment:
    payment_id: str
    status: str
    confirmation_url: str


def is_configured() -> bool:
    return bool(config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY)


def _require_settings() -> tuple[str, str]:
    if not is_configured():
        raise ValidationError("YooKassa is not configured")
    return str(config.YOOKASSA_SHOP_ID), str(config.YOOKASSA_SECRET_KEY)


def _amount_value(amount_rub: int) -> str:
    return f"{Decimal(amount_rub):.2f}"


def _period_days(billing_period: str) -> int:
    if billing_period == "month":
        return 30
    if billing_period == "year":
        return 365
    raise ValidationError("Unsupported billing period")


def _plan_price(plan, billing_period: str) -> int:
    if billing_period == "month":
        return int(plan.monthly_price_rub)
    if billing_period == "year" and plan.yearly_price_rub is not None:
        return int(plan.yearly_price_rub)
    raise ValidationError("Selected billing period is not available for this plan")


def _metadata_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if value is None:
        raise ValidationError(f"YooKassa payment metadata is missing {key}")
    return str(value)


def _decimal_from_payment(payment: dict[str, Any]) -> Decimal:
    try:
        return Decimal(str(payment["amount"]["value"]))
    except (KeyError, InvalidOperation) as exc:
        raise ValidationError("YooKassa payment amount is invalid") from exc


def _int_metadata_value(metadata: dict[str, Any], key: str) -> int:
    try:
        return int(_metadata_value(metadata, key))
    except ValueError as exc:
        raise ValidationError(f"YooKassa payment metadata {key} is invalid") from exc


async def _payment_already_processed(
    session: AsyncSession,
    *,
    tenant_id: int,
    payment_id: str,
) -> bool:
    result = await session.execute(
        select(BillingEvent.new_state)
        .where(BillingEvent.tenant_id == tenant_id, BillingEvent.action == "grant")
        .order_by(BillingEvent.id.desc())
    )
    for state in result.scalars().all():
        if (
            isinstance(state, dict)
            and state.get("provider") == billing_service.PROVIDER_YOOKASSA
            and state.get("provider_payment_id") == payment_id
        ):
            return True
    return False


async def _request_yookassa(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    idempotence_key: str | None = None,
) -> dict[str, Any]:
    shop_id, secret_key = _require_settings()
    headers = {}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key

    async with httpx.AsyncClient(
        base_url=config.YOOKASSA_API_URL.rstrip("/"),
        auth=(shop_id, secret_key),
        timeout=config.YOOKASSA_TIMEOUT_SECONDS,
    ) as client:
        try:
            response = await client.request(method, path, json=json, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail: Any
            try:
                detail = exc.response.json()
            except ValueError:
                detail = exc.response.text
            raise YooKassaError(f"YooKassa API error: {detail}") from exc
        except httpx.HTTPError as exc:
            raise YooKassaError("YooKassa API request failed") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise YooKassaError("YooKassa API returned invalid JSON") from exc


async def create_checkout_payment(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    plan_code: str,
    billing_period: str,
) -> CheckoutPayment:
    if current_tenant.tenant_id is None:
        raise ValidationError("Tenant context required for checkout")

    await billing_service.ensure_default_plans(session)
    plan = await billing_service.get_plan(session, plan_code)
    if plan.code == billing_service.PLAN_START:
        raise ValidationError("The start plan does not require payment")
    if not plan.is_public:
        raise ValidationError("Selected plan is not available for checkout")

    amount_rub = _plan_price(plan, billing_period)
    if amount_rub <= 0:
        raise ValidationError("Selected plan does not require payment")

    tenant = current_tenant.tenant or await session.get(Tenant, current_tenant.tenant_id)
    tenant_name = tenant.name if tenant is not None else f"tenant #{current_tenant.tenant_id}"
    days = _period_days(billing_period)
    return_url = config.YOOKASSA_RETURN_URL or config.MINI_APP_URL
    description = f"TutorBase: тариф {plan.name}, {days} дней"

    payment = await _request_yookassa(
        "POST",
        "/payments",
        idempotence_key=str(uuid.uuid4()),
        json={
            "amount": {"value": _amount_value(amount_rub), "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": {
                "tenant_id": str(current_tenant.tenant_id),
                "tenant_name": tenant_name[:128],
                "plan_code": plan.code,
                "billing_period": billing_period,
                "duration_days": str(days),
            },
        },
    )

    confirmation_url = payment.get("confirmation", {}).get("confirmation_url")
    if not confirmation_url:
        raise YooKassaError("YooKassa did not return a confirmation URL")

    return CheckoutPayment(
        payment_id=str(payment["id"]),
        status=str(payment["status"]),
        confirmation_url=str(confirmation_url),
    )


async def get_payment(payment_id: str) -> dict[str, Any]:
    return await _request_yookassa("GET", f"/payments/{payment_id}")


async def process_webhook(session: AsyncSession, payload: dict[str, Any]) -> None:
    event = str(payload.get("event") or "")
    if event not in {"payment.succeeded", "payment.canceled", "payment.waiting_for_capture", "refund.succeeded"}:
        return

    obj = payload.get("object")
    if not isinstance(obj, dict):
        raise ValidationError("YooKassa webhook object is invalid")

    if event == "refund.succeeded":
        return

    payment_id = obj.get("id")
    if not payment_id:
        raise ValidationError("YooKassa webhook payment id is missing")

    payment = await get_payment(str(payment_id))
    if event != "payment.succeeded":
        return

    if payment.get("status") != "succeeded" or payment.get("paid") is not True:
        return

    metadata = payment.get("metadata")
    if not isinstance(metadata, dict):
        raise ValidationError("YooKassa payment metadata is invalid")

    tenant_id = _int_metadata_value(metadata, "tenant_id")
    plan_code = _metadata_value(metadata, "plan_code")
    billing_period = _metadata_value(metadata, "billing_period")
    days = _int_metadata_value(metadata, "duration_days")
    if days != _period_days(billing_period):
        raise ValidationError("YooKassa payment period metadata is inconsistent")

    await billing_service.ensure_default_plans(session)
    plan = await billing_service.get_plan(session, plan_code)
    expected_amount = Decimal(_amount_value(_plan_price(plan, billing_period)))
    if _decimal_from_payment(payment) != expected_amount:
        raise ValidationError("YooKassa payment amount does not match the selected plan")

    subscription = await billing_service.get_subscription(session, tenant_id)
    if (
        subscription is not None
        and subscription.provider == billing_service.PROVIDER_YOOKASSA
        and subscription.provider_payment_id == str(payment_id)
    ):
        return
    if await _payment_already_processed(session, tenant_id=tenant_id, payment_id=str(payment_id)):
        return

    now = billing_service.utc_now()
    period_start = now
    if (
        subscription is not None
        and subscription.plan_code == plan_code
        and subscription.current_period_end is not None
    ):
        current_end = billing_service._as_aware(subscription.current_period_end)
        if current_end is not None and current_end > now:
            period_start = current_end

    await billing_service.grant_subscription(
        session,
        tenant_id,
        plan_code=plan_code,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=period_start,
        current_period_end=period_start + timedelta(days=days),
        provider=billing_service.PROVIDER_YOOKASSA,
        provider_payment_id=str(payment_id),
        actor_user_id=None,
        notes="Activated from YooKassa payment.succeeded",
    )
