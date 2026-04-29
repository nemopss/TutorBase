from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    amount_due: str
    billing_action: str


@dataclass(frozen=True)
class CheckoutQuote:
    plan_code: str
    plan_name: str
    billing_period: str
    billing_action: str
    amount_due: Decimal
    full_amount: Decimal
    credit_amount: Decimal
    current_plan_code: str | None
    current_plan_name: str | None
    resulting_period_start: datetime
    resulting_period_end: datetime
    message: str


def is_configured() -> bool:
    return bool(config.YOOKASSA_SHOP_ID and config.YOOKASSA_SECRET_KEY)


def _require_settings() -> tuple[str, str]:
    if not is_configured():
        raise ValidationError("YooKassa is not configured")
    return str(config.YOOKASSA_SHOP_ID), str(config.YOOKASSA_SECRET_KEY)


def _money(value: Decimal | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amount_value(amount_rub: Decimal | int) -> str:
    return f"{_money(amount_rub):.2f}"


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


def _plan_amount(plan, billing_period: str) -> Decimal:
    return _money(_plan_price(plan, billing_period))


def _is_active_paid_subscription(subscription, now) -> bool:
    if subscription is None or subscription.plan_code == billing_service.PLAN_START:
        return False
    if subscription.status not in {
        billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        billing_service.SUBSCRIPTION_STATUS_MANUAL,
    }:
        return False
    period_end = billing_service._as_aware(subscription.current_period_end)
    return period_end is not None and period_end > now


def _is_lifetime_paid_subscription(subscription) -> bool:
    return (
        subscription is not None
        and subscription.plan_code != billing_service.PLAN_START
        and subscription.status in {
            billing_service.SUBSCRIPTION_STATUS_ACTIVE,
            billing_service.SUBSCRIPTION_STATUS_MANUAL,
        }
        and billing_service._as_aware(subscription.current_period_end) is None
    )


def _prorated_period_amount(*, amount: Decimal, billing_period: str, period_end, now) -> Decimal:
    remaining_seconds = int((period_end - now).total_seconds())
    if remaining_seconds <= 0:
        return Decimal("0.00")
    period_seconds = _period_days(billing_period) * 24 * 60 * 60
    prorated_amount = amount * Decimal(remaining_seconds) / Decimal(period_seconds)
    return _money(prorated_amount)


async def create_checkout_quote(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    plan_code: str,
    billing_period: str,
) -> CheckoutQuote:
    if current_tenant.tenant_id is None:
        raise ValidationError("Tenant context required for checkout")

    await billing_service.ensure_default_plans(session)
    plan = await billing_service.get_plan(session, plan_code)
    if plan.code == billing_service.PLAN_START:
        raise ValidationError("The start plan does not require payment")
    if not plan.is_public:
        raise ValidationError("Selected plan is not available for checkout")

    days = _period_days(billing_period)
    now = billing_service.utc_now()
    full_amount = _plan_amount(plan, billing_period)
    if full_amount <= 0:
        raise ValidationError("Selected plan does not require payment")

    subscription = await billing_service.get_subscription(session, current_tenant.tenant_id)
    if _is_lifetime_paid_subscription(subscription):
        raise ValidationError("У кабинета уже есть бессрочная платная подписка")

    if not _is_active_paid_subscription(subscription, now):
        return CheckoutQuote(
            plan_code=plan.code,
            plan_name=plan.name,
            billing_period=billing_period,
            billing_action="new",
            amount_due=full_amount,
            full_amount=full_amount,
            credit_amount=Decimal("0.00"),
            current_plan_code=None,
            current_plan_name=None,
            resulting_period_start=now,
            resulting_period_end=now + timedelta(days=days),
            message=f"Тариф «{plan.name}» включится на 30 дней после оплаты.",
        )

    current_plan = await billing_service.get_plan(session, subscription.plan_code)
    current_period_end = billing_service._as_aware(subscription.current_period_end)
    if subscription.plan_code == plan.code:
        resulting_period_start = current_period_end
        resulting_period_end = current_period_end + timedelta(days=days)
        max_renewal_period_end = now + timedelta(days=days * 2)
        if resulting_period_end > max_renewal_period_end:
            raise ValidationError(
                "Продление доступно ближе к окончанию текущего периода. "
                f"Сейчас подписку можно продлить максимум до {(max_renewal_period_end.date()).isoformat()}."
            )
        return CheckoutQuote(
            plan_code=plan.code,
            plan_name=plan.name,
            billing_period=billing_period,
            billing_action="renewal",
            amount_due=full_amount,
            full_amount=full_amount,
            credit_amount=Decimal("0.00"),
            current_plan_code=current_plan.code,
            current_plan_name=current_plan.name,
            resulting_period_start=resulting_period_start,
            resulting_period_end=resulting_period_end,
            message=f"Продлим тариф «{plan.name}» ещё на 30 дней от текущей даты окончания.",
        )

    if plan.display_order < current_plan.display_order:
        raise ValidationError("Переход на тариф ниже доступен после окончания текущего оплаченного периода")

    if current_period_end is None:
        raise ValidationError("Cannot calculate prorated upgrade for the current subscription")

    current_amount = _plan_amount(current_plan, billing_period)
    target_remaining_amount = _prorated_period_amount(
        amount=full_amount,
        billing_period=billing_period,
        period_end=current_period_end,
        now=now,
    )
    credit_amount = _prorated_period_amount(
        amount=current_amount,
        billing_period=billing_period,
        period_end=current_period_end,
        now=now,
    )
    amount_due = max(Decimal("1.00"), _money(target_remaining_amount - credit_amount))
    return CheckoutQuote(
        plan_code=plan.code,
        plan_name=plan.name,
        billing_period=billing_period,
        billing_action="upgrade",
        amount_due=amount_due,
        full_amount=full_amount,
        credit_amount=credit_amount,
        current_plan_code=current_plan.code,
        current_plan_name=current_plan.name,
        resulting_period_start=now,
        resulting_period_end=current_period_end,
        message=(
            f"Перейдём с «{current_plan.name}» на «{plan.name}» сразу. "
            f"Доплата рассчитана за оставшиеся дни текущего оплаченного периода."
        ),
    )


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


def _datetime_metadata_value(metadata: dict[str, Any], key: str) -> datetime:
    value = _metadata_value(metadata, key)
    try:
        return datetime.fromisoformat(value)
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
    quote = await create_checkout_quote(
        session,
        current_tenant,
        plan_code=plan_code,
        billing_period=billing_period,
    )

    tenant = current_tenant.tenant or await session.get(Tenant, current_tenant.tenant_id)
    tenant_name = tenant.name if tenant is not None else f"tenant #{current_tenant.tenant_id}"
    return_url = config.YOOKASSA_RETURN_URL or config.MINI_APP_URL
    description = f"TutorBase: тариф {quote.plan_name}, 30 дней"

    payment = await _request_yookassa(
        "POST",
        "/payments",
        idempotence_key=str(uuid.uuid4()),
        json={
            "amount": {"value": _amount_value(quote.amount_due), "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": {
                "tenant_id": str(current_tenant.tenant_id),
                "tenant_name": tenant_name[:128],
                "plan_code": quote.plan_code,
                "billing_period": quote.billing_period,
                "billing_action": quote.billing_action,
                "duration_days": str(_period_days(quote.billing_period)),
                "charged_amount": _amount_value(quote.amount_due),
                "full_amount": _amount_value(quote.full_amount),
                "credit_amount": _amount_value(quote.credit_amount),
                "period_start": quote.resulting_period_start.isoformat(),
                "period_end": quote.resulting_period_end.isoformat(),
                "previous_plan_code": quote.current_plan_code or "",
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
        amount_due=_amount_value(quote.amount_due),
        billing_action=quote.billing_action,
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
    billing_action = metadata.get("billing_action") or "new"
    days = _int_metadata_value(metadata, "duration_days")
    if days != _period_days(billing_period):
        raise ValidationError("YooKassa payment period metadata is inconsistent")

    await billing_service.ensure_default_plans(session)
    plan = await billing_service.get_plan(session, plan_code)
    expected_amount = Decimal(str(metadata.get("charged_amount") or _amount_value(_plan_price(plan, billing_period))))
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

    period_start = billing_service.utc_now()
    period_end = period_start + timedelta(days=days)
    if isinstance(metadata.get("period_start"), str) and isinstance(metadata.get("period_end"), str):
        period_start = billing_service._as_aware(_datetime_metadata_value(metadata, "period_start"))
        period_end = billing_service._as_aware(_datetime_metadata_value(metadata, "period_end"))
    elif (
        billing_action == "renewal"
        and subscription is not None
        and subscription.plan_code == plan_code
        and subscription.current_period_end is not None
    ):
        current_end = billing_service._as_aware(subscription.current_period_end)
        if current_end is not None and current_end > period_start:
            period_start = current_end
            period_end = period_start + timedelta(days=days)

    await billing_service.grant_subscription(
        session,
        tenant_id,
        plan_code=plan_code,
        status=billing_service.SUBSCRIPTION_STATUS_ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
        provider=billing_service.PROVIDER_YOOKASSA,
        provider_payment_id=str(payment_id),
        actor_user_id=None,
        notes="Activated from YooKassa payment.succeeded",
    )
