"""Data Transfer Objects for service layer.

This module contains DTO classes used to transfer data between layers
(database -> service -> API). DTOs provide a clean interface and decouple
database models from API responses.

DTOs:
    - LearnerDTO: Learner data for display
    - LessonDTO: Lesson data with package and learner info
    - PackageProgress: Progress metrics for lesson packages
    - LessonPackageDTO: Package data with progress
    - TemplateDTO: Template data for package creation
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LearnerDTO:
    """Learner data transfer object.
    
    Attributes:
        id: Learner ID
        display_name: Learner display name
    """
    id: int
    display_name: str


@dataclass(slots=True)
class LessonDTO:
    """Lesson data transfer object.
    
    Contains lesson data with related package and learner information
    for display in API responses.
    
    Attributes:
        id: Lesson ID
        package_id: Parent package ID
        package_title: Package title for display
        learner_name: Learner name for display
        scheduled_at: Scheduled datetime in local timezone
        status: Lesson status (scheduled, completed, cancelled, missed)
        duration_minutes: Lesson duration in minutes
        sequence_index: Order in package
        teacher_notes: Notes from teacher
        homework_due_at: Homework deadline in local timezone
        timezone: Timezone for datetime display
        price: Lesson price (for standalone lessons)
    """
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
    timezone: str
    price: Optional[float] = None


@dataclass(slots=True)
class PackageProgress:
    """Package progress metrics.
    
    Tracks lesson completion statistics for a package.
    Used to display progress indicators in UI.
    
    Attributes:
        total: Total number of lessons in package
        completed: Number of completed lessons
        cancelled: Number of cancelled lessons
    """
    total: int
    completed: int
    cancelled: int


@dataclass(slots=True)
class PackageBalance:
    """Lesson availability and payment balance for a package."""

    purchased: int
    completed: int
    scheduled: int
    cancelled: int
    remaining: int
    available_to_schedule: int
    amount_total: float
    amount_paid: float
    amount_due: float


@dataclass(slots=True)
class LessonPackageDTO:
    """Lesson package data transfer object.
    
    Contains package data with progress metrics and learner information
    for display in API responses and UI.
    
    Attributes:
        id: Package ID
        learner_id: ID of learner assigned to package
        learner_name: Learner display name
        template_id: ID of template used to create package (if any)
        package_type: Package type (package, one_off)
        title: Package title/name
        status: Package status (active, completed, cancelled)
        start_date: Package start date in local timezone
        end_date: Package end date in local timezone
        timezone: Timezone for datetime display
        notes: Additional notes about package
        total_lessons: Total number of lessons in package
        progress: Progress metrics (total, completed, cancelled)
        price: Package price (calculated or manual)
        payment_status: Payment status (unpaid, partial, paid)
        total_paid: Total amount paid for this package
    """
    id: int
    learner_id: int
    learner_name: Optional[str]
    template_id: Optional[int]
    package_type: str
    schedule_mode: str
    renewal_enabled: bool
    title: str
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    timezone: str
    notes: Optional[str]
    total_lessons: Optional[int]
    progress: PackageProgress
    price: Optional[float] = None
    payment_status: str = 'unpaid'
    total_paid: float = 0.0
    next_lesson_date: Optional[datetime] = None
    balance: Optional[PackageBalance] = None


@dataclass(slots=True)
class TemplateDTO:
    """Template data transfer object.
    
    Contains template configuration for creating lesson packages.
    Templates define default settings for package creation including
    lesson count, schedule, and reminder rules.
    
    Attributes:
        id: Template ID
        name: Template name for display
        description: Detailed description of template purpose
        lesson_count: Default number of lessons in packages created from template
        duration_days: Default duration in days for package schedule
        timezone: Default timezone for lesson scheduling
        default_config: Additional configuration as JSON (lesson frequency, reminders, etc.)
    """
    id: int
    name: str
    description: Optional[str]
    lesson_count: Optional[int]
    duration_days: Optional[int]
    timezone: str
    default_config: Optional[dict]
