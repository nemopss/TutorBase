"""Pydantic schemas for learner endpoints.

This module provides request/response models for learner operations,
including validation rules for learner creation, updates, and responses.

Key components:
    - CreateLearnerRequest: Schema for creating new learners
    - CreateLearnerFromChatIdRequest: Schema for creating learners from Telegram chat
    - UpdateLearnerRequest: Schema for updating existing learners
    - UpdateLearnerNotificationsRequest: Schema for toggling notifications
    - LearnerResponse: Schema for learner API responses

Validation rules:
    - Display name must be non-empty (1-255 chars)
    - Notes limited to 5000 chars
    - Chat ID must be positive for Telegram integration
    - Bot user ID must be positive
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin


class LearnerResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for learner.
    
    Returned by API endpoints when fetching or creating learners.
    Includes all learner details and related bot user information.
    
    Attributes:
        id: Learner ID
        display_name: Display name for the learner
        notifications_enabled: Whether learner receives notifications
        chat_id: Telegram chat ID (if linked to bot user)
        bot_user_id: ID of linked bot user
        notes: Teacher notes about the learner
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="Learner ID")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    notifications_enabled: bool = Field(default=True, description="Whether notifications are enabled")
    chat_id: Optional[int] = Field(None, description="Telegram chat ID")
    bot_user_id: Optional[int] = Field(None, gt=0, description="Linked bot user ID")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")


class LearnerListResponse(BaseResponse):
    """Response schema for learner list.
    
    Note: This is deprecated in favor of PaginatedResponse[LearnerResponse].
    Kept for backward compatibility.
    
    Attributes:
        items: List of learners
    """
    items: list[LearnerResponse] = Field(..., description="List of learners")


class CreateLearnerRequest(BaseRequest):
    """Request schema for creating a new learner.
    
    Validates all required fields and business rules for learner creation.
    
    Attributes:
        bot_user_id: ID of bot user to link (required, must be positive)
        display_name: Display name for learner (required, 1-255 chars)
        notes: Optional teacher notes (max 5000 chars)
        notifications_enabled: Whether to enable notifications (default: True)
    
    Validation:
        - bot_user_id must be positive
        - display_name must be non-empty and <= 255 chars
        - notes max 5000 chars
    """
    bot_user_id: int = Field(..., gt=0, description="Bot user ID to link")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name for learner")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    notifications_enabled: bool = Field(default=True, description="Enable notifications")

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """Validate and trim display name.
        
        Args:
            v: Display name to validate
            
        Returns:
            Trimmed display name
            
        Raises:
            ValueError: If display name is empty after trimming
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Display name cannot be empty or whitespace only")
        return trimmed


class CreateLearnerFromChatIdRequest(BaseRequest):
    """Request schema for creating a learner from Telegram chat ID.
    
    This is a convenience endpoint that creates or finds a bot user
    by chat_id and then creates a learner linked to that bot user.
    
    Attributes:
        chat_id: Telegram chat ID (required)
        display_name: Display name for learner (required, 1-255 chars)
        notes: Optional teacher notes (max 5000 chars)
        notifications_enabled: Whether to enable notifications (default: True)
    
    Validation:
        - chat_id is required
        - display_name must be non-empty and <= 255 chars
        - notes max 5000 chars
    """
    chat_id: int = Field(..., description="Telegram chat ID")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name for learner")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    notifications_enabled: bool = Field(
        default=True,
        description="Whether learner should receive notifications after creation",
    )

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """Validate and trim display name.
        
        Args:
            v: Display name to validate
            
        Returns:
            Trimmed display name
            
        Raises:
            ValueError: If display name is empty after trimming
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Display name cannot be empty or whitespace only")
        return trimmed


class UpdateLearnerRequest(BaseRequest):
    """Request schema for updating an existing learner.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        display_name: New display name (1-255 chars)
        notes: New teacher notes (max 5000 chars)
        notifications_enabled: New notification setting
    
    Validation:
        - If provided, display_name must be non-empty and <= 255 chars
        - If provided, notes max 5000 chars
    """
    display_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Display name")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    notifications_enabled: Optional[bool] = Field(None, description="Enable or disable notifications")

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and trim display name.
        
        Args:
            v: Display name to validate
            
        Returns:
            Trimmed display name or None
            
        Raises:
            ValueError: If display name is empty after trimming
        """
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Display name cannot be empty or whitespace only")
        return trimmed


class UpdateLearnerNotificationsRequest(BaseRequest):
    """Request schema for updating learner notification settings.
    
    Convenience endpoint for toggling notifications without full update.
    
    Attributes:
        notifications_enabled: Whether to enable or disable notifications
    """
    notifications_enabled: bool = Field(..., description="Enable or disable notifications")


__all__ = [
    'LearnerResponse',
    'LearnerListResponse',
    'CreateLearnerRequest',
    'CreateLearnerFromChatIdRequest',
    'UpdateLearnerRequest',
    'UpdateLearnerNotificationsRequest',
]
