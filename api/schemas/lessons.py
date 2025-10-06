from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LessonResponse(BaseModel):
    id: int
    package_id: int
    scheduled_at: datetime
    status: str
    duration_minutes: Optional[int]
    sequence_index: Optional[int]
    teacher_notes: Optional[str]
    homework_due_at: Optional[datetime]


class LessonListResponse(BaseModel):
    total: int
    items: list[LessonResponse]


class LessonCreateRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: Optional[int] = None
    status: str = Field(default="scheduled")
    teacher_notes: Optional[str] = None
    homework_due_at: Optional[datetime] = None


class LessonUpdateRequest(BaseModel):
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    teacher_notes: Optional[str] = None
    homework_due_at: Optional[datetime] = None

