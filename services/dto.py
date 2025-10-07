from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LearnerDTO:
    id: int
    display_name: str


@dataclass(slots=True)
class LessonDTO:
    id: int
    package_id: int
    package_title: Optional[str]
    learner_name: Optional[str]
    scheduled_at: datetime
    status: str
    duration_minutes: Optional[int]
    sequence_index: Optional[int]
    teacher_notes: Optional[str]
    homework_due_at: Optional[datetime]


@dataclass(slots=True)
class PackageProgress:
    total: int
    completed: int
    cancelled: int


@dataclass(slots=True)
class LessonPackageDTO:
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
    progress: PackageProgress


@dataclass(slots=True)
class TemplateDTO:
    id: int
    name: str
    description: Optional[str]
    lesson_count: Optional[int]
    duration_days: Optional[int]
    timezone: str
    default_config: Optional[dict]



