from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


AnalyticsSeverity = Literal["info", "warning", "critical"]
AnalyticsInsightCategory = Literal["learner", "package", "finance", "notifications", "workload"]
AnalyticsInsightCode = Literal[
    "no_future_learners",
    "high_cancellation_rate",
    "ending_packages",
    "outstanding_balance",
    "notification_failures",
    "no_telegram_learners",
    "no_critical_issues",
]


class AnalyticsMetricComparison(BaseModel):
    current: float = Field(..., description="Current period value")
    previous: float = Field(..., description="Previous equal-length period value")
    delta: float = Field(..., description="Absolute delta")
    change_percent: float | None = Field(None, description="Percent change; null when previous value is zero")


class AnalyticsSummary(BaseModel):
    active_learners: int
    completed_lessons: int
    planned_lessons: int
    cancelled_lessons: int
    completed_hours: float
    planned_hours: float
    cash_revenue: Decimal
    earned_revenue: Decimal
    planned_revenue: Decimal
    outstanding_revenue: Decimal
    cancellation_rate: float
    notification_delivery_rate: float


class AnalyticsTimePoint(BaseModel):
    date: date
    completed_lessons: int
    planned_lessons: int
    cancelled_lessons: int
    completed_hours: float
    planned_hours: float
    cash_revenue: Decimal
    earned_revenue: Decimal
    reminders_scheduled: int
    reminders_delivered: int
    reminders_failed: int


class AnalyticsWeekdayPoint(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="ISO weekday index, Monday=0")
    completed_lessons: int
    planned_lessons: int
    cancelled_lessons: int
    completed_hours: float
    planned_hours: float


class AnalyticsLearnerBreakdown(BaseModel):
    learner_id: int
    learner_name: str
    completed_lessons: int
    planned_lessons: int
    cancelled_lessons: int
    completed_hours: float
    planned_hours: float
    cash_revenue: Decimal
    earned_revenue: Decimal
    planned_revenue: Decimal
    outstanding_revenue: Decimal
    cancellation_rate: float
    has_future_lessons: bool
    risk_flags: list[str]


class AnalyticsPackageBreakdown(BaseModel):
    package_id: int
    package_title: str
    learner_id: int
    learner_name: str
    status: str
    total_lessons: int
    completed_lessons: int
    cancelled_lessons: int
    remaining_lessons: int
    progress_percent: float
    next_lesson_at: datetime | None
    last_lesson_at: datetime | None
    ends_soon: bool
    risk_flags: list[str]


class AnalyticsNotifications(BaseModel):
    total_scheduled: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    failed_learners_count: int
    no_telegram_learners_count: int


class AnalyticsInsight(BaseModel):
    code: AnalyticsInsightCode
    category: AnalyticsInsightCategory
    severity: AnalyticsSeverity
    title: str
    detail: str
    action_label: str | None = None
    target_path: str | None = None
    metric_value: float | None = None


class AnalyticsOverviewResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    previous_period_start: datetime
    previous_period_end: datetime
    summary: AnalyticsSummary
    comparisons: dict[str, AnalyticsMetricComparison]
    timeseries: list[AnalyticsTimePoint]
    weekday_load: list[AnalyticsWeekdayPoint]
    learners: list[AnalyticsLearnerBreakdown]
    packages: list[AnalyticsPackageBreakdown]
    notifications: AnalyticsNotifications
    insights: list[AnalyticsInsight]
