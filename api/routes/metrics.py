from __future__ import annotations

from datetime import datetime, date, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_session,
    require_maintenance_tenant_access,
)
from api.schemas import (
    DashboardAttentionDismissalRequest,
    DashboardAttentionDismissalResponse,
    DashboardHistoryResponse,
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


def _dashboard_attention_dismissal_response(
    dismissal,
) -> DashboardAttentionDismissalResponse:
    return DashboardAttentionDismissalResponse(
        id=dismissal.id,
        item_type=dismissal.item_type,
        item_key=dismissal.item_key,
        dismissed_until=dismissal.dismissed_until,
        created_at=dismissal.created_at,
        updated_at=dismissal.updated_at,
    )


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


@router.get("/dashboard-history", response_model=DashboardHistoryResponse)
async def dashboard_history_metrics(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> DashboardHistoryResponse:
    history = await crud.fetch_dashboard_history_metrics(session, current_tenant)
    return DashboardHistoryResponse.model_validate(history)


@router.get(
    "/dashboard-attention-dismissals",
    response_model=list[DashboardAttentionDismissalResponse],
)
async def list_dashboard_attention_dismissals(
    item_type: str | None = Query(None, max_length=64),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[DashboardAttentionDismissalResponse]:
    dismissals = await crud.fetch_active_dashboard_attention_dismissals(
        session,
        current_tenant,
        reference_time=datetime.now(timezone.utc),
        item_type=item_type,
    )
    return [_dashboard_attention_dismissal_response(item) for item in dismissals]


@router.post(
    "/dashboard-attention-dismissals",
    response_model=DashboardAttentionDismissalResponse,
)
async def dismiss_dashboard_attention_item(
    payload: DashboardAttentionDismissalRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_maintenance_tenant_access),
) -> DashboardAttentionDismissalResponse:
    dismissal = await crud.upsert_dashboard_attention_dismissal(
        session,
        current_tenant,
        item_type=payload.item_type,
        item_key=payload.item_key,
        dismissed_until=payload.dismissed_until,
    )
    await session.commit()
    await session.refresh(dismissal)
    return _dashboard_attention_dismissal_response(dismissal)
