from __future__ import annotations

from datetime import datetime, date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, get_current_tenant, CurrentTenant
from api.schemas import (
    DailyMetricsResponse,
    MetricsSummary,
    DailyPoint,
)
from database import crud

router = APIRouter()


def _coerce_row_to_date(raw: datetime | date | str) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        return date.fromisoformat(raw)
    return date.fromisoformat(str(raw))


@router.get("/summary", response_model=MetricsSummary)
async def metrics_summary(
    from_date: datetime | None = Query(None, description="Filter lessons from this date"),
    to_date: datetime | None = Query(None, description="Filter lessons to this date"),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> MetricsSummary:
    lessons = await crud.count_lessons_by_status(session, current_tenant, from_date=from_date, to_date=to_date)
    reminders = await crud.count_reminders_by_status(session, current_tenant)
    return MetricsSummary(lessons=lessons, reminders=reminders)


@router.get("/lessons/daily", response_model=DailyMetricsResponse)
async def lessons_daily_metrics(
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> DailyMetricsResponse:
    rows = await crud.lessons_daily_stats(session, current_tenant, from_date=from_date, to_date=to_date)
    points = [DailyPoint(date=_coerce_row_to_date(row[0]), value=row[1]) for row in rows if row[0] is not None]
    return DailyMetricsResponse(items=points)


@router.get("/reminders/daily", response_model=DailyMetricsResponse)
async def reminders_daily_metrics(
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> DailyMetricsResponse:
    rows = await crud.reminders_daily_stats(session, current_tenant, from_date=from_date, to_date=to_date)
    points = [DailyPoint(date=_coerce_row_to_date(row[0]), value=row[1]) for row in rows if row[0] is not None]
    return DailyMetricsResponse(items=points)