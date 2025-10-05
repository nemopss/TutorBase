from __future__ import annotations

from datetime import datetime, date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required
from api.schemas import (
    DailyMetricsResponse,
    MetricsSummary,
    DailyPoint,
)
from database import crud

router = APIRouter()


@router.get("/summary", response_model=MetricsSummary)
async def metrics_summary(
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> MetricsSummary:
    lessons = await crud.count_lessons_by_status(session)
    reminders = await crud.count_reminders_by_status(session)
    return MetricsSummary(lessons=lessons, reminders=reminders)


@router.get("/lessons/daily", response_model=DailyMetricsResponse)
async def lessons_daily_metrics(
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> DailyMetricsResponse:
    rows = await crud.lessons_daily_stats(session, from_date=from_date, to_date=to_date)
    points = [DailyPoint(date=date.fromisoformat(row[0]), value=row[1]) for row in rows]
    return DailyMetricsResponse(items=points)


@router.get("/reminders/daily", response_model=DailyMetricsResponse)
async def reminders_daily_metrics(
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> DailyMetricsResponse:
    rows = await crud.reminders_daily_stats(session, from_date=from_date, to_date=to_date)
    points = [DailyPoint(date=date.fromisoformat(row[0]), value=row[1]) for row in rows]
    return DailyMetricsResponse(items=points)
