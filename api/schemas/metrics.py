from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class MetricsSummary(BaseModel):
    lessons: dict[str, int]
    reminders: dict[str, int]


class DailyPoint(BaseModel):
    date: date
    value: int


class DailyMetricsResponse(BaseModel):
    items: list[DailyPoint]

