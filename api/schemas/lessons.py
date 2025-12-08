"""Pydantic schemas for lesson endpoints.

This module provides request/response models for lesson operations,
including validation rules for lesson creation, updates, and responses.

Key components:
    - LessonCreateRequest: Schema for creating new lessons
    - LessonUpdateRequest: Schema for updating existing lessons
    - LessonResponse: Schema for lesson API responses

Validation rules:
    - Status must be one of: scheduled, rescheduled, completed, cancelled, missed
    - Duration must be positive (1-480 minutes, i.e., up to 8 hours)
    - Scheduled date must be provided
    - Teacher notes limited to 5000 chars
    - Homework due date must be after scheduled date
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator, model_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin
from api.schemas.validators import validate_status

# Valid lesson statuses
VALID_LESSON_STATUSES = ['scheduled', 'rescheduled', 'completed', 'cancelled', 'missed']


class LessonResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for lesson.
    
    Returned by API endpoints when fetching or creating lessons.
    Includes all lesson details and related package/learner information.
    
    Attributes:
        id: Lesson ID
        package_id: ID of parent lesson package
        package_title: Title of parent package
        learner_name: Display name of learner
        scheduled_at: Scheduled lesson datetime
        status: Current status (scheduled, rescheduled, completed, cancelled, missed)
        duration_minutes: Lesson duration in minutes
        sequence_index: Order of lesson in package
        teacher_notes: Notes from teacher
        homework_due_at: Homework deadline
        timezone: Timezone for scheduling
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="Lesson ID")
    package_id: int = Field(..., gt=0, description="Parent package ID")
    package_title: Optional[str] = Field(None, description="Parent package title")
    learner_name: Optional[str] = Field(None, description="Learner display name")
    scheduled_at: datetime = Field(..., description="Scheduled lesson datetime")
    status: str = Field(..., description="Lesson status")
    duration_minutes: Optional[int] = Field(None, gt=0, le=480, description="Duration in minutes")
    sequence_index: Optional[int] = Field(None, ge=0, description="Order in package")
    teacher_notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    homework_due_at: Optional[datetime] = Field(None, description="Homework deadline")
    timezone: str = Field(..., description="Timezone for scheduling")


class LessonListResponse(BaseResponse):
    """Response schema for paginated lesson list.
    
    Note: This is deprecated in favor of PaginatedResponse[LessonResponse].
    Kept for backward compatibility.
    
    Attributes:
        total: Total number of lessons
        items: List of lessons
    """
    total: int = Field(ge=0, description="Total number of lessons")
    items: list[LessonResponse] = Field(..., description="List of lessons")


class LessonCreateRequest(BaseRequest):
    """Request schema for creating a new lesson.
    
    Validates all required fields and business rules for lesson creation.
    
    Attributes:
        scheduled_at: Scheduled lesson datetime (required)
        duration_minutes: Lesson duration in minutes (1-480, default: None)
        status: Lesson status (default: scheduled)
        teacher_notes: Optional teacher notes (max 5000 chars)
        homework_due_at: Optional homework deadline
    
    Validation:
        - scheduled_at is required
        - duration_minutes must be between 1 and 480 (8 hours)
        - status must be one of: scheduled, rescheduled, completed, cancelled, missed
        - teacher_notes max 5000 chars
        - homework_due_at must be after scheduled_at if provided
    """
    scheduled_at: datetime = Field(..., description="Scheduled lesson datetime")
    duration_minutes: Optional[int] = Field(None, gt=0, le=480, description="Duration in minutes (max 8 hours)")
    status: str = Field(default='scheduled', description="Lesson status")
    teacher_notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    homework_due_at: Optional[datetime] = Field(None, description="Homework deadline")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: str) -> str:
        """Validate lesson status is one of allowed values.
        
        Args:
            v: Status value to validate
            
        Returns:
            Validated status
            
        Raises:
            ValueError: If status is not in allowed list
        """
        return validate_status(v, VALID_LESSON_STATUSES)

    @model_validator(mode='after')
    def validate_homework_due_after_scheduled(self) -> 'LessonCreateRequest':
        """Validate that homework_due_at is after scheduled_at if provided.
        
        Returns:
            Self with validated dates
            
        Raises:
            ValueError: If homework_due_at is before or equal to scheduled_at
        """
        if self.homework_due_at is not None and self.scheduled_at is not None:
            if self.homework_due_at <= self.scheduled_at:
                raise ValueError("Homework due date must be after scheduled lesson time")
        return self


class LessonUpdateRequest(BaseRequest):
    """Request schema for updating an existing lesson.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        scheduled_at: New scheduled datetime
        duration_minutes: New duration in minutes (1-480)
        status: New lesson status
        teacher_notes: New teacher notes (max 5000 chars)
        homework_due_at: New homework deadline
    
    Validation:
        - If provided, duration_minutes must be between 1 and 480
        - If provided, status must be one of: scheduled, rescheduled, completed, cancelled, missed
        - If provided, teacher_notes max 5000 chars
        - If both dates provided, homework_due_at must be after scheduled_at
    """
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled lesson datetime")
    duration_minutes: Optional[int] = Field(None, gt=0, le=480, description="Duration in minutes (max 8 hours)")
    status: Optional[str] = Field(None, description="Lesson status")
    teacher_notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    homework_due_at: Optional[datetime] = Field(None, description="Homework deadline")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate lesson status is one of allowed values.
        
        Args:
            v: Status value to validate
            
        Returns:
            Validated status or None
            
        Raises:
            ValueError: If status is not in allowed list
        """
        if v is None:
            return v
        return validate_status(v, VALID_LESSON_STATUSES)

    @model_validator(mode='after')
    def validate_homework_due_after_scheduled(self) -> 'LessonUpdateRequest':
        """Validate that homework_due_at is after scheduled_at if both provided.
        
        Returns:
            Self with validated dates
            
        Raises:
            ValueError: If homework_due_at is before or equal to scheduled_at
        """
        if self.homework_due_at is not None and self.scheduled_at is not None:
            if self.homework_due_at <= self.scheduled_at:
                raise ValueError("Homework due date must be after scheduled lesson time")
        return self


__all__ = [
    'LessonResponse',
    'LessonListResponse',
    'LessonCreateRequest',
    'LessonUpdateRequest',
    'VALID_LESSON_STATUSES',
]
