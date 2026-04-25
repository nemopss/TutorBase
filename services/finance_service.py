"""Service for managing financial operations.

This module contains business logic for financial tracking including:
- Package price calculation based on learner rates
- Payment recording and status management
- Outstanding balance calculation
- Income reporting and dashboard metrics

Key components:
    - calculate_package_price: Calculate package price from rate and lessons
    - update_payment_status: Update package payment status based on payments
    - record_payment: Record a new payment
    - get_outstanding_balance: Calculate learner's outstanding balance
    - get_dashboard_metrics: Get aggregated financial metrics
    - generate_income_report: Generate income report for date range

Business logic:
    - Package price = learner_rate × total_lessons
    - Payment status: unpaid (0), partial (0 < paid < price), paid (paid >= price)
    - Outstanding balance = sum of billable package prices minus all learner payments
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.prometheus_metrics import (
    payments_recorded_amount_total,
    payments_recorded_total,
    payments_voided_amount_total,
    payments_voided_total,
)
from database.models import Learner, LessonPackage, Lesson, Payment, PaymentAuditEvent

if TYPE_CHECKING:
    from api.dependencies import CurrentTenant


DEBT_PACKAGE_STATUSES: tuple[str, ...] = ("active", "completed")
PACKAGE_TYPE_PACKAGE = "package"


def _payment_metric_currency(currency: str | None) -> str:
    return (currency or "UNKNOWN").upper()


def _package_charge_expr():
    imputed_package_price = Learner.lesson_rate * LessonPackage.total_lessons
    return case(
        (
            LessonPackage.price.isnot(None) & (LessonPackage.price > Decimal("0")),
            LessonPackage.price,
        ),
        (
            (LessonPackage.package_type == PACKAGE_TYPE_PACKAGE)
            & Learner.lesson_rate.isnot(None)
            & LessonPackage.total_lessons.isnot(None)
            & (LessonPackage.total_lessons > 0),
            imputed_package_price,
        ),
        else_=Decimal("0"),
    )


def _serialize_payment(payment: Payment) -> dict[str, Any]:
    return {
        "learner_id": payment.learner_id,
        "package_id": payment.package_id,
        "lesson_id": payment.lesson_id,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "notes": payment.notes,
        "voided_at": payment.voided_at.isoformat() if payment.voided_at else None,
        "void_reason": payment.void_reason,
    }


async def _record_payment_event(
    session: AsyncSession,
    *,
    payment: Payment,
    actor_user_id: int | None,
    action: str,
    previous_state: dict[str, Any] | None,
    notes: str | None = None,
) -> None:
    session.add(
        PaymentAuditEvent(
            payment_id=payment.id,
            tenant_id=payment.tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            previous_state=previous_state,
            new_state=_serialize_payment(payment),
            notes=notes,
        )
    )


def calculate_package_price(
    learner_rate: Decimal | None,
    total_lessons: int | None,
) -> Decimal | None:
    """Calculate package price from learner rate and lesson count.
    
    Implements Property 1: Package Price Calculation.
    For any learner with lesson_rate R and package with total_lessons N,
    the calculated price SHALL equal R × N.
    
    Args:
        learner_rate: Individual lesson rate for the learner (can be None)
        total_lessons: Total number of lessons in the package (can be None)
    
    Returns:
        Calculated price as Decimal, or None if rate or lessons is None
    
    **Validates: Requirements 2.1, 2.2**
    """
    if learner_rate is None or total_lessons is None:
        return None
    if total_lessons <= 0:
        return Decimal("0")
    return learner_rate * total_lessons



async def update_payment_status(
    session: AsyncSession,
    package_id: int,
) -> str:
    """Recalculate and update package payment status based on payments.
    
    Implements Property 2: Payment Status Consistency.
    For any package with price P and total payments T:
    - IF T = 0 THEN payment_status = 'unpaid'
    - IF 0 < T < P THEN payment_status = 'partial'
    - IF T >= P THEN payment_status = 'paid'
    
    Args:
        session: Async database session
        package_id: ID of the package to update
    
    Returns:
        New payment status string ('unpaid', 'partial', or 'paid')
    
    **Validates: Requirements 3.3, 3.4, 3.5**
    """
    # Get package - refresh to ensure we have latest data
    package = await session.get(LessonPackage, package_id)
    if not package:
        return 'unpaid'
    
    # Refresh package to ensure we're working with latest DB state
    await session.refresh(package)
    
    # Sum all payments for this tenant/package pair.
    result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == package.tenant_id,
            Payment.package_id == package_id,
            Payment.voided_at.is_(None),
        )
    )
    total_paid_raw = result.scalar()
    
    # Determine status - ensure both are Decimal with same precision for proper comparison
    # Round to 2 decimal places to avoid floating point comparison issues
    package_price = Decimal(str(package.price)).quantize(Decimal("0.01")) if package.price else Decimal("0")
    total_paid = Decimal(str(total_paid_raw)).quantize(Decimal("0.01")) if total_paid_raw else Decimal("0")
    
    if total_paid <= Decimal("0"):
        new_status = 'unpaid'
    elif total_paid >= package_price and package_price > Decimal("0"):
        new_status = 'paid'
    else:
        new_status = 'partial'
    
    # Update package
    package.payment_status = new_status
    await session.flush()
    
    return new_status


def determine_payment_status(
    total_paid: Decimal,
    package_price: Decimal | None,
) -> str:
    """Determine payment status based on paid amount and price.
    
    Pure function for testing payment status logic without database.
    
    Args:
        total_paid: Total amount paid
        package_price: Package price (can be None)
    
    Returns:
        Payment status string ('unpaid', 'partial', or 'paid')
    """
    price = package_price or Decimal("0")
    
    if total_paid <= Decimal("0"):
        return 'unpaid'
    elif price > Decimal("0") and total_paid >= price:
        return 'paid'
    elif total_paid > Decimal("0"):
        return 'partial'
    return 'unpaid'



async def record_payment(
    session: AsyncSession,
    current_tenant: "CurrentTenant",
    *,
    learner_id: int,
    amount: Decimal,
    paid_at: datetime,
    package_id: int | None = None,
    lesson_id: int | None = None,
    notes: str | None = None,
    currency: str = "RUB",
    actor_user_id: int | None = None,
) -> Payment:
    """Record a new payment and update related package status.
    
    Creates a Payment record and updates the package's payment_status
    if the payment is associated with a package.
    
    Implements Property 5: Payment Recording Integrity.
    For any recorded payment, retrieving that payment SHALL return
    the same amount, date, and associations that were provided.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of the learner making the payment
        amount: Payment amount (must be positive)
        paid_at: Date/time of payment
        package_id: Associated package ID (optional)
        lesson_id: Associated lesson ID for standalone lessons (optional)
        notes: Optional payment notes
        currency: Currency code (default 'RUB')
    
    Returns:
        Created Payment record
    
    Raises:
        ValueError: If amount is not positive
    
    **Validates: Requirements 3.1, 3.2**
    """
    if amount <= Decimal("0"):
        raise ValueError("Amount must be positive")
    
    now = datetime.utcnow()
    
    payment = Payment(
        tenant_id=current_tenant.tenant_id,
        learner_id=learner_id,
        package_id=package_id,
        lesson_id=lesson_id,
        amount=amount,
        currency=currency,
        paid_at=paid_at,
        notes=notes,
        updated_by_user_id=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    
    session.add(payment)
    await session.flush()
    
    # Update package payment status if payment is for a package
    if package_id is not None:
        await update_payment_status(session, package_id)

    await _record_payment_event(
        session,
        payment=payment,
        actor_user_id=actor_user_id,
        action="create",
        previous_state=None,
        notes=notes,
    )
    metric_currency = _payment_metric_currency(payment.currency)
    payments_recorded_total.labels(currency=metric_currency).inc()
    payments_recorded_amount_total.labels(currency=metric_currency).inc(float(payment.amount))

    return payment


async def update_payment(
    session: AsyncSession,
    payment: Payment,
    *,
    amount: Decimal | None,
    paid_at: datetime | None,
    notes: str | None,
    actor_user_id: int | None,
) -> Payment:
    previous_state = _serialize_payment(payment)
    now = datetime.utcnow()

    if amount is not None:
        if amount <= Decimal("0"):
            raise ValueError("Amount must be positive")
        payment.amount = amount
    if paid_at is not None:
        payment.paid_at = paid_at
    if notes is not None:
        payment.notes = notes

    payment.updated_by_user_id = actor_user_id
    payment.updated_at = now
    session.add(payment)
    await session.flush()

    if payment.package_id is not None:
        await update_payment_status(session, payment.package_id)

    await _record_payment_event(
        session,
        payment=payment,
        actor_user_id=actor_user_id,
        action="update",
        previous_state=previous_state,
        notes=notes,
    )
    return payment


async def void_payment(
    session: AsyncSession,
    payment: Payment,
    *,
    actor_user_id: int | None,
    reason: str | None = None,
) -> Payment:
    if payment.voided_at is not None:
        return payment

    previous_state = _serialize_payment(payment)
    now = datetime.utcnow()
    payment.voided_at = now
    payment.voided_by_user_id = actor_user_id
    payment.void_reason = reason
    payment.updated_by_user_id = actor_user_id
    payment.updated_at = now
    session.add(payment)
    await session.flush()

    if payment.package_id is not None:
        await update_payment_status(session, payment.package_id)

    await _record_payment_event(
        session,
        payment=payment,
        actor_user_id=actor_user_id,
        action="void",
        previous_state=previous_state,
        notes=reason,
    )
    metric_currency = _payment_metric_currency(payment.currency)
    payments_voided_total.labels(currency=metric_currency).inc()
    payments_voided_amount_total.labels(currency=metric_currency).inc(float(payment.amount))
    return payment



async def get_outstanding_balance(
    session: AsyncSession,
    current_tenant: "CurrentTenant",
    learner_id: int,
) -> Decimal:
    """Calculate total outstanding balance for a learner.
    
    Implements Property 3: Outstanding Balance Calculation.
    For any learner, outstanding_balance SHALL equal the sum of billable package
    prices minus all non-voided learner payments.
    The calculation intentionally does not trust payment_status, because that
    field is a denormalized cache and can become stale after manual data fixes.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of the learner
    
    Returns:
        Total outstanding balance as Decimal
    
    **Validates: Requirements 5.2, 5.3**
    """
    # Compute learner-level balance. Unassigned payments must reduce debt too:
    # tutors often record one payment for several one-off lessons.
    # Debt rules (docs/saas-platform-plan.md):
    # - only active/completed packages create debt
    # - draft/cancelled packages do not create debt
    # - legacy package rows with missing price still create debt when the price
    #   can be derived from learner rate and lesson count.
    charge_expr = _package_charge_expr()
    charges_result = await session.execute(
        select(func.coalesce(func.sum(charge_expr), Decimal("0")))
        .join(Learner, Learner.id == LessonPackage.learner_id)
        .where(
            LessonPackage.tenant_id == current_tenant.tenant_id,
            LessonPackage.learner_id == learner_id,
            LessonPackage.status.in_(DEBT_PACKAGE_STATUSES),
            charge_expr > Decimal("0"),
        )
    )
    total_charges = charges_result.scalar() or Decimal("0")

    if total_charges <= Decimal("0"):
        return Decimal("0")

    payments_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.learner_id == learner_id,
            Payment.voided_at.is_(None),
        )
    )
    total_paid = payments_result.scalar() or Decimal("0")

    outstanding = total_charges - total_paid
    return outstanding if outstanding > Decimal("0") else Decimal("0")



@dataclass
class MonthlyIncome:
    """Monthly income data point."""
    month: str  # Format: "2025-01"
    amount: Decimal


@dataclass
class DashboardMetrics:
    """Financial dashboard metrics."""
    current_month_income: Decimal
    previous_month_income: Decimal
    total_outstanding: Decimal
    unpaid_learners_count: int
    income_chart: list[MonthlyIncome]


async def get_dashboard_metrics(
    session: AsyncSession,
    current_tenant: "CurrentTenant",
) -> DashboardMetrics:
    """Get aggregated financial metrics for dashboard.
    
    Calculates:
    - Current month income (sum of payments)
    - Previous month income
    - Total outstanding balance across all learners
    - Count of learners with unpaid packages
    - 6-month income chart data
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
    
    Returns:
        DashboardMetrics with all calculated values
    
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    from datetime import timezone
    from dateutil.relativedelta import relativedelta
    
    now = datetime.now(timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = current_month_start - relativedelta(months=1)
    six_months_ago = current_month_start - relativedelta(months=5)
    
    # Current month income
    current_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= current_month_start,
            Payment.voided_at.is_(None),
        )
    )
    current_month_income = current_result.scalar() or Decimal("0")
    
    # Previous month income
    previous_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= previous_month_start,
            Payment.paid_at < current_month_start,
            Payment.voided_at.is_(None),
        )
    )
    previous_month_income = previous_result.scalar() or Decimal("0")
    
    # Total outstanding balance.
    # Compute from learner-level facts: billable charges minus all non-voided
    # learner payments. This lets one unassigned payment cover several lessons.
    charge_expr = _package_charge_expr()
    charges_by_learner = (
        select(
            LessonPackage.learner_id.label("learner_id"),
            func.coalesce(func.sum(charge_expr), Decimal("0")).label("total_charges"),
        )
        .join(Learner, Learner.id == LessonPackage.learner_id)
        .where(
            LessonPackage.tenant_id == current_tenant.tenant_id,
            LessonPackage.status.in_(DEBT_PACKAGE_STATUSES),
            charge_expr > Decimal("0"),
        )
        .group_by(LessonPackage.learner_id)
        .subquery()
    )

    payments_by_learner = (
        select(
            Payment.learner_id.label("learner_id"),
            func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total_paid"),
        )
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.voided_at.is_(None),
        )
        .group_by(Payment.learner_id)
        .subquery()
    )

    charges_expr = func.coalesce(charges_by_learner.c.total_charges, Decimal("0"))
    paid_expr = func.coalesce(payments_by_learner.c.total_paid, Decimal("0"))
    diff_expr = charges_expr - paid_expr
    outstanding_expr = case((diff_expr > Decimal("0"), diff_expr), else_=Decimal("0"))

    debtors_agg = (
        select(
            func.coalesce(func.sum(outstanding_expr), Decimal("0")).label("total_outstanding"),
            func.count().label("unpaid_learners_count"),
        )
        .select_from(charges_by_learner)
        .outerjoin(
            payments_by_learner,
            payments_by_learner.c.learner_id == charges_by_learner.c.learner_id,
        )
        .where(outstanding_expr > Decimal("0"))
    )
    debtors_row = (await session.execute(debtors_agg)).one()
    total_outstanding = debtors_row.total_outstanding or Decimal("0")
    unpaid_learners_count = int(debtors_row.unpaid_learners_count or 0)
    
    # 6-month income chart
    income_chart: list[MonthlyIncome] = []
    for i in range(6):
        month_start = current_month_start - relativedelta(months=5-i)
        month_end = month_start + relativedelta(months=1)
        
        month_result = await session.execute(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
            .where(
                Payment.tenant_id == current_tenant.tenant_id,
                Payment.paid_at >= month_start,
                Payment.paid_at < month_end,
                Payment.voided_at.is_(None),
            )
        )
        month_income = month_result.scalar() or Decimal("0")
        income_chart.append(MonthlyIncome(
            month=month_start.strftime("%Y-%m"),
            amount=month_income,
        ))
    
    return DashboardMetrics(
        current_month_income=current_month_income,
        previous_month_income=previous_month_income,
        total_outstanding=total_outstanding,
        unpaid_learners_count=unpaid_learners_count,
        income_chart=income_chart,
    )


@dataclass
class Debtor:
    learner_id: int
    learner_name: str
    outstanding_balance: Decimal


async def get_debtors(
    session: AsyncSession,
    current_tenant: "CurrentTenant",
    *,
    limit: int,
    offset: int,
) -> tuple[list[Debtor], int]:
    """List learners with outstanding balance.

    Must match dashboard debt calculation and debt rules.
    """
    charge_expr = _package_charge_expr()
    charges_by_learner = (
        select(
            LessonPackage.learner_id.label("learner_id"),
            func.coalesce(func.sum(charge_expr), Decimal("0")).label("total_charges"),
        )
        .join(Learner, Learner.id == LessonPackage.learner_id)
        .where(
            LessonPackage.tenant_id == current_tenant.tenant_id,
            LessonPackage.status.in_(DEBT_PACKAGE_STATUSES),
            charge_expr > Decimal("0"),
        )
        .group_by(LessonPackage.learner_id)
        .subquery()
    )

    payments_by_learner = (
        select(
            Payment.learner_id.label("learner_id"),
            func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total_paid"),
        )
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.voided_at.is_(None),
        )
        .group_by(Payment.learner_id)
        .subquery()
    )

    charges_expr = func.coalesce(charges_by_learner.c.total_charges, Decimal("0"))
    paid_expr = func.coalesce(payments_by_learner.c.total_paid, Decimal("0"))
    diff_expr = charges_expr - paid_expr
    outstanding_expr = case((diff_expr > Decimal("0"), diff_expr), else_=Decimal("0"))

    base = (
        select(
            Learner.id.label("learner_id"),
            Learner.display_name.label("learner_name"),
            outstanding_expr.label("outstanding_balance"),
        )
        .join(charges_by_learner, charges_by_learner.c.learner_id == Learner.id)
        .outerjoin(
            payments_by_learner,
            payments_by_learner.c.learner_id == Learner.id,
        )
        .where(
            Learner.tenant_id == current_tenant.tenant_id,
            outstanding_expr > Decimal("0"),
        )
    )

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    rows = (
        await session.execute(
            base.order_by(outstanding_expr.desc(), Learner.display_name.asc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    items = [
        Debtor(
            learner_id=row.learner_id,
            learner_name=row.learner_name or "Unknown",
            outstanding_balance=row.outstanding_balance or Decimal("0"),
        )
        for row in rows
    ]
    return items, int(total)



@dataclass
class LearnerIncome:
    """Income breakdown by learner."""
    learner_id: int
    learner_name: str
    amount: Decimal


@dataclass
class PackageIncome:
    """Income breakdown by package."""
    package_id: int
    package_title: str
    amount: Decimal


@dataclass
class IncomeReport:
    """Income report for a date range."""
    period_start: datetime
    period_end: datetime
    total: Decimal
    by_learner: list[LearnerIncome]
    by_package: list[PackageIncome]
    previous_period_total: Decimal
    change_percent: float


async def generate_income_report(
    session: AsyncSession,
    current_tenant: "CurrentTenant",
    from_date: datetime,
    to_date: datetime,
) -> IncomeReport:
    """Generate income report for date range.
    
    Implements Property 6: Income Report Date Filtering.
    For any income report with date range [from_date, to_date],
    the total SHALL equal the sum of all payments where paid_at
    is within that range (inclusive).
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        from_date: Start of date range (inclusive)
        to_date: End of date range (inclusive)
    
    Returns:
        IncomeReport with totals and breakdowns
    
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    from dateutil.relativedelta import relativedelta
    
    # Calculate period length for previous period comparison
    period_length = to_date - from_date
    previous_from = from_date - period_length - relativedelta(days=1)
    previous_to = from_date - relativedelta(days=1)
    
    # Total income for current period
    total_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= from_date,
            Payment.paid_at <= to_date,
            Payment.voided_at.is_(None),
        )
    )
    total = total_result.scalar() or Decimal("0")
    
    # Previous period total
    previous_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= previous_from,
            Payment.paid_at <= previous_to,
            Payment.voided_at.is_(None),
        )
    )
    previous_period_total = previous_result.scalar() or Decimal("0")
    
    # Calculate change percent
    if previous_period_total > Decimal("0"):
        change_percent = float((total - previous_period_total) / previous_period_total * 100)
    else:
        change_percent = 100.0 if total > Decimal("0") else 0.0
    
    # Breakdown by learner
    learner_result = await session.execute(
        select(
            Payment.learner_id,
            Learner.display_name,
            func.sum(Payment.amount).label('amount')
        )
        .join(Learner, Payment.learner_id == Learner.id)
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= from_date,
            Payment.paid_at <= to_date,
            Payment.voided_at.is_(None),
        )
        .group_by(Payment.learner_id, Learner.display_name)
        .order_by(func.sum(Payment.amount).desc())
    )
    by_learner = [
        LearnerIncome(
            learner_id=row.learner_id,
            learner_name=row.display_name or "Unknown",
            amount=row.amount or Decimal("0"),
        )
        for row in learner_result.all()
    ]
    
    # Breakdown by package
    package_result = await session.execute(
        select(
            Payment.package_id,
            LessonPackage.title,
            func.sum(Payment.amount).label('amount')
        )
        .outerjoin(LessonPackage, Payment.package_id == LessonPackage.id)
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.paid_at >= from_date,
            Payment.paid_at <= to_date,
            Payment.package_id.isnot(None),
            Payment.voided_at.is_(None),
        )
        .group_by(Payment.package_id, LessonPackage.title)
        .order_by(func.sum(Payment.amount).desc())
    )
    by_package = [
        PackageIncome(
            package_id=row.package_id,
            package_title=row.title or "Unknown",
            amount=row.amount or Decimal("0"),
        )
        for row in package_result.all()
    ]
    
    return IncomeReport(
        period_start=from_date,
        period_end=to_date,
        total=total,
        by_learner=by_learner,
        by_package=by_package,
        previous_period_total=previous_period_total,
        change_percent=change_percent,
    )
