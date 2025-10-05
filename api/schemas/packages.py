from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PackageProgressModel(BaseModel):
    total: int
    completed: int
    cancelled: int


class PackageResponse(BaseModel):
    id: int
    learner_id: int
    learner_name: Optional[str]
    template_id: Optional[int]
    title: str
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    timezone: str
    notes: Optional[str]
    total_lessons: Optional[int]
    progress: PackageProgressModel


class PackageListResponse(BaseModel):
    total: int
    items: list[PackageResponse]


class PackageCreateRequest(BaseModel):
    learner_id: int
    title: str
    notes: Optional[str] = None
    status: str = Field(default="draft")
    template_id: Optional[int] = None
    start_date: Optional[datetime] = None
    timezone: Optional[str] = None
    total_lessons: Optional[int] = None


class PackageUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    timezone: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_lessons: Optional[int] = None

