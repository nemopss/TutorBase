from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database.models import BillingEvent, BillingPlan, Learner, Tenant, TenantSubscription
from services.exceptions import NotFoundError, ValidationError

PLAN_START = "start"
PLAN_BASIC = "basic"
PLAN_PRO = "pro"
PLAN_STUDIO = "studio"

SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_MANUAL = "manual"
SUBSCRIPTION_STATUS_CANCELED = "canceled"
SUBSCRIPTION_STATUS_PAST_DUE = "past_due"
SUBSCRIPTION_STATUS_SUSPENDED = "suspended"

PROVIDER_MANUAL = "manual"
PROVIDER_YOOKASSA = "yookassa"

REASON_ACTIVE = "active"
REASON_FREE_PLAN = "free_plan"
REASON_NO_SUBSCRIPTION = "no_subscription"
REASON_SUBSCRIPTION_EXPIRED = "subscription_expired"
REASON_SUBSCRIPTION_EXPIRED_OVER_FREE_LIMIT = "subscription_expired_over_free_limit"
REASON_PAST_DUE_GRACE = "past_due_grace"
REASON_CANCELED_PERIOD_ACTIVE = "canceled_period_active"


DEFAULT_PLANS: tuple[dict[str, Any], ...] = (
    {
        "code": PLAN_START,
        "name": "Старт",
        "active_learners_limit": 5,
        "monthly_price_rub": 0,
        "yearly_price_rub": None,
        "display_order": 10,
    },
    {
        "code": PLAN_BASIC,
        "name": "Базовый",
        "active_learners_limit": 10,
        "monthly_price_rub": 349,
        "yearly_price_rub": 3490,
        "display_order": 20,
    },
    {
        "code": PLAN_PRO,
        "name": "Про",
        "active_learners_limit": 20,
        "monthly_price_rub": 649,
        "yearly_price_rub": 6490,
        "display_order": 30,
    },
    {
        "code": PLAN_STUDIO,
        "name": "Бизнес",
        "active_learners_limit": 50,
        "monthly_price_rub": 1190,
        "yearly_price_rub": 11900,
        "display_order": 40,
    },
)


@dataclass(frozen=True)
class BillingSnapshot:
    tenant_id: int
    plan_code: str
    plan_name: str
    subscription_plan_code: str | None
    subscription_status: str | None
    provider: str | None
    active_learners_limit: int
    active_learners_count: int
    monthly_price_rub: int
    yearly_price_rub: int | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    grace_until: datetime | None
    cancel_at_period_end: bool
    is_effective_free_plan: bool
    is_over_limit: bool
    can_create_learner: bool
    can_restore_learner: bool
    notifications_allowed: bool
    billing_restriction_reason: str | None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _default_plan_record(code: str) -> dict[str, Any]:
    for plan in DEFAULT_PLANS:
        if plan["code"] == code:
            return plan
    raise KeyError(code)


def _plan_from_default(code: str) -> BillingPlan:
    data = _default_plan_record(code)
    return BillingPlan(
        code=data["code"],
        name=data["name"],
        active_learners_limit=data["active_learners_limit"],
        monthly_price_rub=data["monthly_price_rub"],
        yearly_price_rub=data["yearly_price_rub"],
        display_order=data["display_order"],
        is_public=True,
    )


async def ensure_default_plans(session: AsyncSession) -> None:
    existing = await session.execute(select(BillingPlan.code))
    existing_codes = set(existing.scalars().all())
    now = utc_now()
    for data in DEFAULT_PLANS:
        if data["code"] in existing_codes:
            continue
        session.add(
            BillingPlan(
                code=data["code"],
                name=data["name"],
                active_learners_limit=data["active_learners_limit"],
                monthly_price_rub=data["monthly_price_rub"],
                yearly_price_rub=data["yearly_price_rub"],
                display_order=data["display_order"],
                is_public=True,
                created_at=now,
                updated_at=now,
            )
        )
    await session.flush()


async def get_plan(session: AsyncSession, code: str) -> BillingPlan:
    plan = await session.get(BillingPlan, code)
    if plan is not None:
        return plan
    if code == PLAN_START:
        return _plan_from_default(PLAN_START)
    raise NotFoundError(f"Billing plan {code} not found")


async def list_public_plans(session: AsyncSession) -> list[BillingPlan]:
    await ensure_default_plans(session)
    result = await session.execute(
        select(BillingPlan)
        .where(BillingPlan.is_public.is_(True))
        .order_by(BillingPlan.display_order.asc())
    )
    return list(result.scalars().all())


async def get_subscription(session: AsyncSession, tenant_id: int) -> TenantSubscription | None:
    result = await session.execute(
        select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def ensure_subscription(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_user_id: int | None = None,
    notes: str | None = None,
) -> TenantSubscription:
    subscription = await get_subscription(session, tenant_id)
    if subscription is not None:
        return subscription

    await ensure_default_plans(session)
    now = utc_now()
    subscription = TenantSubscription(
        tenant_id=tenant_id,
        plan_code=PLAN_START,
        status=SUBSCRIPTION_STATUS_ACTIVE,
        provider=PROVIDER_MANUAL,
        cancel_at_period_end=False,
        notes=notes,
        updated_by_user_id=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(subscription)
    await session.flush()
    await _record_event(
        session,
        subscription=subscription,
        actor_user_id=actor_user_id,
        action="created",
        previous_state=None,
        notes=notes,
    )
    return subscription


async def count_active_learners(session: AsyncSession, tenant_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Learner)
        .where(Learner.tenant_id == tenant_id, Learner.archived_at.is_(None))
    )
    return int(result.scalar() or 0)


async def get_billing_snapshot(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    active_learners_count: int | None = None,
) -> BillingSnapshot | None:
    if current_tenant.tenant_id is None:
        return None
    return await get_billing_snapshot_for_tenant(
        session,
        current_tenant.tenant_id,
        active_learners_count=active_learners_count,
    )


async def get_billing_snapshot_for_tenant(
    session: AsyncSession,
    tenant_id: int,
    *,
    active_learners_count: int | None = None,
    now: datetime | None = None,
) -> BillingSnapshot:
    now = now or utc_now()
    subscription = await get_subscription(session, tenant_id)
    active_count = (
        active_learners_count
        if active_learners_count is not None
        else await count_active_learners(session, tenant_id)
    )

    start_plan = await get_plan(session, PLAN_START)
    effective_plan = start_plan
    reason: str | None = REASON_NO_SUBSCRIPTION if subscription is None else None

    if subscription is not None:
        subscription_plan = await get_plan(session, subscription.plan_code)
        period_end = _as_aware(subscription.current_period_end)
        grace_until = _as_aware(subscription.grace_until)

        if subscription.plan_code == PLAN_START:
            effective_plan = start_plan
            reason = REASON_FREE_PLAN
        elif subscription.status in {SUBSCRIPTION_STATUS_ACTIVE, SUBSCRIPTION_STATUS_MANUAL}:
            if period_end is None or now <= period_end:
                effective_plan = subscription_plan
                reason = REASON_ACTIVE
            else:
                effective_plan = start_plan
                reason = REASON_SUBSCRIPTION_EXPIRED
        elif subscription.status == SUBSCRIPTION_STATUS_CANCELED:
            if period_end is not None and now <= period_end:
                effective_plan = subscription_plan
                reason = REASON_CANCELED_PERIOD_ACTIVE
            else:
                effective_plan = start_plan
                reason = REASON_SUBSCRIPTION_EXPIRED
        elif subscription.status == SUBSCRIPTION_STATUS_PAST_DUE:
            if grace_until is not None and now <= grace_until:
                effective_plan = subscription_plan
                reason = REASON_PAST_DUE_GRACE
            else:
                effective_plan = start_plan
                reason = REASON_SUBSCRIPTION_EXPIRED
        else:
            effective_plan = start_plan
            reason = subscription.status

    is_over_limit = active_count > effective_plan.active_learners_limit
    is_over_start_limit = (
        effective_plan.code == PLAN_START
        and active_count > start_plan.active_learners_limit
    )
    is_expired_over_free_limit = (
        is_over_start_limit
        and reason in {REASON_SUBSCRIPTION_EXPIRED, REASON_NO_SUBSCRIPTION}
    )
    notifications_allowed = not is_over_start_limit
    restriction_reason = (
        REASON_SUBSCRIPTION_EXPIRED_OVER_FREE_LIMIT
        if is_expired_over_free_limit
        else (reason if is_over_limit else None)
    )

    return BillingSnapshot(
        tenant_id=tenant_id,
        plan_code=effective_plan.code,
        plan_name=effective_plan.name,
        subscription_plan_code=subscription.plan_code if subscription is not None else None,
        subscription_status=subscription.status if subscription is not None else None,
        provider=subscription.provider if subscription is not None else None,
        active_learners_limit=effective_plan.active_learners_limit,
        active_learners_count=active_count,
        monthly_price_rub=effective_plan.monthly_price_rub,
        yearly_price_rub=effective_plan.yearly_price_rub,
        current_period_start=_as_aware(subscription.current_period_start) if subscription is not None else None,
        current_period_end=_as_aware(subscription.current_period_end) if subscription is not None else None,
        grace_until=_as_aware(subscription.grace_until) if subscription is not None else None,
        cancel_at_period_end=bool(subscription.cancel_at_period_end) if subscription is not None else False,
        is_effective_free_plan=effective_plan.code == PLAN_START,
        is_over_limit=is_over_limit,
        can_create_learner=active_count < effective_plan.active_learners_limit,
        can_restore_learner=active_count < effective_plan.active_learners_limit,
        notifications_allowed=notifications_allowed,
        billing_restriction_reason=restriction_reason,
    )


async def assert_can_create_learner(session: AsyncSession, current_tenant: CurrentTenant) -> None:
    snapshot = await get_billing_snapshot(session, current_tenant)
    if snapshot is None or snapshot.can_create_learner:
        return
    raise ValidationError(_learner_limit_message(snapshot))


async def assert_can_restore_learner(session: AsyncSession, current_tenant: CurrentTenant) -> None:
    snapshot = await get_billing_snapshot(session, current_tenant)
    if snapshot is None or snapshot.can_restore_learner:
        return
    raise ValidationError(_learner_limit_message(snapshot))


async def notifications_allowed_for_tenant(session: AsyncSession, tenant_id: int) -> bool:
    snapshot = await get_billing_snapshot_for_tenant(session, tenant_id)
    return snapshot.notifications_allowed


async def grant_subscription(
    session: AsyncSession,
    tenant_id: int,
    *,
    plan_code: str,
    status: str = SUBSCRIPTION_STATUS_MANUAL,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
    grace_until: datetime | None = None,
    provider: str = PROVIDER_MANUAL,
    provider_customer_id: str | None = None,
    provider_payment_id: str | None = None,
    provider_subscription_id: str | None = None,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantSubscription:
    await _get_tenant_or_404(session, tenant_id)
    await ensure_default_plans(session)
    await get_plan(session, plan_code)
    subscription = await ensure_subscription(session, tenant_id, actor_user_id=actor_user_id)
    previous_state = _serialize_subscription(subscription)
    now = utc_now()
    subscription.plan_code = plan_code
    subscription.status = status
    subscription.provider = provider
    subscription.current_period_start = current_period_start
    subscription.current_period_end = current_period_end
    subscription.grace_until = grace_until
    subscription.cancel_at_period_end = False
    subscription.provider_customer_id = provider_customer_id
    subscription.provider_payment_id = provider_payment_id
    subscription.provider_subscription_id = provider_subscription_id
    subscription.updated_by_user_id = actor_user_id
    subscription.notes = notes
    subscription.updated_at = now
    await _record_event(
        session,
        subscription=subscription,
        actor_user_id=actor_user_id,
        action="grant",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return subscription


async def cancel_subscription(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantSubscription:
    await _get_tenant_or_404(session, tenant_id)
    subscription = await ensure_subscription(session, tenant_id, actor_user_id=actor_user_id)
    previous_state = _serialize_subscription(subscription)
    now = utc_now()
    subscription.status = SUBSCRIPTION_STATUS_CANCELED
    subscription.cancel_at_period_end = True
    subscription.updated_by_user_id = actor_user_id
    subscription.notes = notes
    subscription.updated_at = now
    await _record_event(
        session,
        subscription=subscription,
        actor_user_id=actor_user_id,
        action="cancel",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return subscription


async def _get_tenant_or_404(session: AsyncSession, tenant_id: int) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return tenant


def _serialize_subscription(subscription: TenantSubscription | None) -> dict[str, Any] | None:
    if subscription is None:
        return None
    return {
        "plan_code": subscription.plan_code,
        "status": subscription.status,
        "provider": subscription.provider,
        "provider_customer_id": subscription.provider_customer_id,
        "provider_payment_id": subscription.provider_payment_id,
        "provider_subscription_id": subscription.provider_subscription_id,
        "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "grace_until": subscription.grace_until.isoformat() if subscription.grace_until else None,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "notes": subscription.notes,
    }


async def _record_event(
    session: AsyncSession,
    *,
    subscription: TenantSubscription,
    actor_user_id: int | None,
    action: str,
    previous_state: dict[str, Any] | None,
    notes: str | None,
) -> None:
    event = BillingEvent(
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        actor_user_id=actor_user_id,
        action=action,
        previous_state=previous_state,
        new_state=_serialize_subscription(subscription),
        notes=notes,
        created_at=utc_now(),
    )
    session.add(event)


def _learner_limit_message(snapshot: BillingSnapshot) -> str:
    return (
        f"Пока нет места для активного ученика: на тарифе «{snapshot.plan_name}» "
        f"доступно {snapshot.active_learners_limit}, сейчас уже {snapshot.active_learners_count}. "
        "Можно освободить место, архивировав неактивного ученика. Данные в архиве сохранятся."
    )
