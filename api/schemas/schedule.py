"""Pydantic schemas for learner schedule endpoints.

This module provides request/response models for schedule operations,
including validation rules for schedule slots.

Key components:
    - ScheduleSlot: Single schedule slot (day, time, duration)
    - LearnerScheduleResponse: Full schedule response
    - UpdateScheduleRequest: Replace entire schedule
    - AddSlotsRequest: Add multiple slots at once
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# Time format regex: HH:MM (24-hour)
TIME_PATTERN = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


class ScheduleSlot(BaseModel):
    """Single schedule slot representing a recurring lesson time.
    
    Attributes:
        day: Day of week (0=Monday, 6=Sunday)
        time: Start time in 24-hour format (HH:MM)
        duration: Lesson duration in minutes
    """
    day: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    duration: int = Field(..., gt=0, le=480, description="Duration in minutes (max 8 hours)")
    
    @field_validator('time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time is in HH:MM 24-hour format.
        
        Args:
            v: Time string to validate
            
        Returns:
            Validated time string
            
        Raises:
            ValueError: If time format is invalid
        """
        if not TIME_PATTERN.match(v):
            raise ValueError("Invalid time format. Use HH:MM (24-hour)")
        return v


class LearnerScheduleResponse(BaseModel):
    """Response schema for learner schedule.
    
    Attributes:
        learner_id: ID of the learner
        slots: List of schedule slots
        timezone: Timezone for the schedule
    """
    learner_id: int = Field(..., description="Learner ID")
    slots: list[ScheduleSlot] = Field(default_factory=list, description="Schedule slots")
    timezone: str = Field(default="Europe/Moscow", description="Schedule timezone")


class UpdateScheduleRequest(BaseModel):
    """Request schema for replacing entire schedule.
    
    Attributes:
        slots: New list of schedule slots
        timezone: Timezone for the schedule
    """
    slots: list[ScheduleSlot] = Field(..., description="Schedule slots")
    timezone: str = Field(default="Europe/Moscow", description="Schedule timezone")


class AddSlotsRequest(BaseModel):
    """Request schema for adding multiple slots at once.
    
    Allows selecting multiple days with the same time and duration.
    Creates separate slots for each selected day.
    
    Attributes:
        days: List of days (0=Monday, 6=Sunday)
        time: Start time in HH:MM format
        duration: Duration in minutes
    """
    days: list[int] = Field(..., min_length=1, description="Days of week (0=Monday, 6=Sunday)")
    time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    duration: int = Field(..., gt=0, le=480, description="Duration in minutes")
    
    @field_validator('days')
    @classmethod
    def validate_days(cls, v: list[int]) -> list[int]:
        """Validate all days are valid (0-6).
        
        Args:
            v: List of days to validate
            
        Returns:
            Validated list of unique days
            
        Raises:
            ValueError: If any day is invalid
        """
        for day in v:
            if day < 0 or day > 6:
                raise ValueError(f"Invalid day: {day}. Must be 0-6 (Monday-Sunday)")
        return list(set(v))  # Remove duplicates
    
    @field_validator('time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time is in HH:MM 24-hour format."""
        if not TIME_PATTERN.match(v):
            raise ValueError("Invalid time format. Use HH:MM (24-hour)")
        return v


__all__ = [
    'ScheduleSlot',
    'LearnerScheduleResponse',
    'UpdateScheduleRequest',
    'AddSlotsRequest',
]


class PreviewDatesRequest(BaseModel):
    """Request schema for generating lesson date preview.
    
    Attributes:
        learner_id: ID of the learner
        start_date: Start date for generating lessons (YYYY-MM-DD)
        lesson_count: Number of lessons to generate
    """
    learner_id: int = Field(..., description="Learner ID")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    lesson_count: int = Field(..., gt=0, le=100, description="Number of lessons to generate")


class PreviewDateItem(BaseModel):
    """Single date in the preview.
    
    Attributes:
        datetime: ISO datetime string
        duration: Duration in minutes
    """
    datetime: str = Field(..., description="ISO datetime string")
    duration: int = Field(..., description="Duration in minutes")


class PreviewDatesResponse(BaseModel):
    """Response schema for lesson date preview.
    
    Attributes:
        dates: List of generated lesson dates
        schedule: The schedule used for generation
    """
    dates: list[PreviewDateItem] = Field(..., description="Generated lesson dates")
    schedule: LearnerScheduleResponse = Field(..., description="Schedule used for generation")
