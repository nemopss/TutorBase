"""Pydantic schemas for reminder endpoints.

This module provides request/response models for reminder operations,
including validation rules for reminder updates and responses.

Key components:
    - ReminderUpdateRequest: Schema for updating reminder instances
    - ReminderResponse: Schema for reminder API responses

Validation rules:
    - Status must be one of: scheduled, sent, confirmed, declined, cancelled
    - Comment limited to 5000 chars
    - Scheduled date must be provided
    - Payload must be valid JSON dict
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import Field, field_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin
from api.schemas.validators import validate_status

# Valid reminder statuses
VALID_REMINDER_STATUSES = ['scheduled', 'sent', 'delivered', 'confirmed', 'declined', 'cancelled']


class ReminderResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for reminder instance.
    
    Returned by API endpoints when fetching or updating reminders.
    Includes all reminder details, status, and interaction history.
    
    Attributes:
        id: Reminder instance ID
        package_id: Parent lesson package ID
        lesson_id: Related lesson ID (if lesson-specific)
        learner_id: Learner to receive reminder
        reminder_type: Type of reminder (lesson_reminder, homework_reminder, etc.)
        scheduled_for: When to send this reminder
        status: Current status (scheduled, sent, confirmed, declined, cancelled)
        active: Whether this reminder is active
        payload: JSON data for reminder content
        comment: Additional comment or context
        last_notified_at: Last notification send timestamp
        last_response: Last response from learner
        last_response_at: Last response timestamp
        last_decline_reason: Reason if learner declined
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="Reminder instance ID")
    package_id: int = Field(..., gt=0, description="Parent package ID")
    lesson_id: Optional[int] = Field(None, gt=0, description="Related lesson ID")
    learner_id: Optional[int] = Field(None, gt=0, description="Learner ID")
    reminder_type: Optional[str] = Field(None, description="Type of reminder")
    scheduled_for: datetime = Field(..., description="Scheduled send time")
    status: str = Field(..., description="Reminder status")
    active: bool = Field(..., description="Whether reminder is active")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Reminder content data")
    comment: Optional[str] = Field(None, max_length=5000, description="Additional comment")
    last_notified_at: Optional[datetime] = Field(None, description="Last notification time")
    last_response: Optional[str] = Field(None, description="Last learner response")
    last_response_at: Optional[datetime] = Field(None, description="Last response time")
    last_decline_reason: Optional[str] = Field(None, max_length=5000, description="Decline reason")


class ReminderListResponse(BaseResponse):
    """Response schema for reminder list.
    
    Note: This is deprecated in favor of PaginatedResponse[ReminderResponse].
    Kept for backward compatibility.
    
    Attributes:
        total: Total number of reminders
        items: List of reminders
    """
    total: int = Field(ge=0, description="Total number of reminders")
    items: list[ReminderResponse] = Field(..., description="List of reminders")


class ReminderUpdateRequest(BaseRequest):
    """Request schema for updating a reminder instance.
    
    All fields are optional - only provided fields will be updated.
    Typically used to update status, activate/deactivate, or add comments.
    
    Attributes:
        status: New reminder status
        active: New active state
        comment: New comment or note
    
    Validation:
        - If provided, status must be one of: scheduled, sent, confirmed, declined, cancelled
        - If provided, comment max 5000 chars
    """
    status: Optional[str] = Field(None, description="Reminder status")
    active: Optional[bool] = Field(None, description="Whether reminder is active")
    comment: Optional[str] = Field(None, max_length=5000, description="Additional comment")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate reminder status is one of allowed values.
        
        Args:
            v: Status value to validate
            
        Returns:
            Validated status or None
            
        Raises:
            ValueError: If status is not in allowed list
        """
        if v is None or v == "":
            return None
        return validate_status(v, VALID_REMINDER_STATUSES)


__all__ = [
    'ReminderResponse',
    'ReminderListResponse',
    'ReminderUpdateRequest',
    'VALID_REMINDER_STATUSES',
]

