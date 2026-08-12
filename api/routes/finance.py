"""Finance API endpoints.

This module provides REST API endpoints for financial operations:
- GET /finance/dashboard - Get dashboard metrics
- GET /finance/reports/income - Get income report
- GET /finance/reports/income/export - Export income report as CSV
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from io import StringIO
import csv
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_session,
)
from api.schemas.finance import (
    DashboardMetricsResponse,
    DebtorResponse,
    MonthlyIncomeResponse,
    IncomeReportResponse,
    LearnerIncomeResponse,
    PackageIncomeResponse,
)
from api.schemas import PaginatedResponse, PaginationParams
from services import finance_service
from utils.timezone import DEFAULT_TZ, to_utc

router = APIRouter()


class ReportPeriod(str, Enum):
    """Report period options."""
    MONTH = "month"
    QUARTER = "quarter"
    CUSTOM = "custom"


def _resolve_report_period(
    period: ReportPeriod,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    now_local = (now or datetime.now(timezone.utc)).astimezone(DEFAULT_TZ)
    if period == ReportPeriod.MONTH:
        start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(timezone.utc), now_local.astimezone(timezone.utc)
    if period == ReportPeriod.QUARTER:
        quarter_month = ((now_local.month - 1) // 3) * 3 + 1
        start_local = now_local.replace(
            month=quarter_month,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return start_local.astimezone(timezone.utc), now_local.astimezone(timezone.utc)
    if not from_date or not to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date and to_date are required for custom period",
        )
    start = to_utc(from_date, DEFAULT_TZ)
    end = to_utc(to_date, DEFAULT_TZ)
    if start > end:
        raise HTTPException(status_code=422, detail="from_date must be before to_date")
    return start, end


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> DashboardMetricsResponse:
    """Get financial dashboard metrics.
    
    Returns:
    - Current month income
    - Previous month income
    - Total outstanding balance
    - Count of learners with unpaid packages
    - 6-month income chart
    
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    """
    metrics = await finance_service.get_dashboard_metrics(session, current_tenant)
    
    return DashboardMetricsResponse(
        current_month_income=metrics.current_month_income,
        previous_month_income=metrics.previous_month_income,
        total_outstanding=metrics.total_outstanding,
        unpaid_learners_count=metrics.unpaid_learners_count,
        income_chart=[
            MonthlyIncomeResponse(month=m.month, amount=m.amount)
            for m in metrics.income_chart
        ],
    )


@router.get("/debtors", response_model=PaginatedResponse[DebtorResponse])
async def list_debtors(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[DebtorResponse]:
    """List learners with outstanding balance.

    The dashboard count and this list MUST use the same debt calculation.
    """
    debtors, total = await finance_service.get_debtors(
        session,
        current_tenant,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    items = [
        DebtorResponse(
            learner_id=item.learner_id,
            learner_name=item.learner_name,
            outstanding_balance=item.outstanding_balance,
        )
        for item in debtors
    ]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.get("/reports/income", response_model=IncomeReportResponse)
async def get_income_report(
    period: ReportPeriod = Query(ReportPeriod.MONTH, description="Report period"),
    from_date: Optional[datetime] = Query(None, description="Custom period start"),
    to_date: Optional[datetime] = Query(None, description="Custom period end"),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> IncomeReportResponse:
    """Get income report for specified period.
    
    Period options:
    - month: Current month
    - quarter: Current quarter
    - custom: Custom date range (requires from_date and to_date)
    
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    start, end = _resolve_report_period(
        period,
        from_date=from_date,
        to_date=to_date,
    )
    
    report = await finance_service.generate_income_report(
        session, current_tenant, start, end
    )
    
    return IncomeReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        total=report.total,
        by_learner=[
            LearnerIncomeResponse(
                learner_id=l.learner_id,
                learner_name=l.learner_name,
                amount=l.amount,
            )
            for l in report.by_learner
        ],
        by_package=[
            PackageIncomeResponse(
                package_id=p.package_id,
                package_title=p.package_title,
                amount=p.amount,
            )
            for p in report.by_package
        ],
        previous_period_total=report.previous_period_total,
        change_percent=report.change_percent,
    )


@router.get("/reports/income/export")
async def export_income_report(
    period: ReportPeriod = Query(ReportPeriod.MONTH, description="Report period"),
    from_date: Optional[datetime] = Query(None, description="Custom period start"),
    to_date: Optional[datetime] = Query(None, description="Custom period end"),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> StreamingResponse:
    """Export income report as CSV file.
    
    **Validates: Requirements 6.5**
    """
    start, end = _resolve_report_period(
        period,
        from_date=from_date,
        to_date=to_date,
    )
    
    report = await finance_service.generate_income_report(
        session, current_tenant, start, end
    )
    
    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Income Report"])
    writer.writerow([f"Period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"])
    writer.writerow([f"Total: {report.total}"])
    writer.writerow([f"Previous Period: {report.previous_period_total}"])
    writer.writerow([f"Change: {report.change_percent:.1f}%"])
    writer.writerow([])
    
    # By Learner
    writer.writerow(["Income by Learner"])
    writer.writerow(["Learner ID", "Learner Name", "Amount"])
    for l in report.by_learner:
        writer.writerow([l.learner_id, l.learner_name, l.amount])
    writer.writerow([])
    
    # By Package
    writer.writerow(["Income by Package"])
    writer.writerow(["Package ID", "Package Title", "Amount"])
    for p in report.by_package:
        writer.writerow([p.package_id, p.package_title, p.amount])
    
    output.seek(0)
    
    filename = f"income_report_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
