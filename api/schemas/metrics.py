from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    lessons: dict[str, int]
    reminders: dict[str, int]


class DailyPoint(BaseModel):
    date: date
    value: int


class DailyMetricsResponse(BaseModel):
    items: list[DailyPoint]


DashboardAttentionItemType = Literal["package_ending_soon", "lesson_declined"]


class DashboardAttentionDismissalRequest(BaseModel):
    item_type: DashboardAttentionItemType
    item_key: str = Field(..., min_length=1, max_length=255)
    dismissed_until: datetime


class DashboardAttentionDismissalResponse(BaseModel):
    id: int
    item_type: DashboardAttentionItemType
    item_key: str
    dismissed_until: datetime
    created_at: datetime
    updated_at: datetime
