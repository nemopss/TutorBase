"""Pydantic schemas for user endpoints.

This module provides request/response models for user operations,
including validation rules for user updates and responses.

Key components:
    - UserResponse: Schema for user API responses
    - UserRoleUpdateRequest: Schema for updating user roles

Validation rules:
    - Role must be one of: admin, teacher, viewer
    - Display name must be non-empty (1-255 chars)
    - Username must be non-empty if provided (1-255 chars)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin

# Valid user roles
UserRole = Literal["admin", "teacher", "viewer"]


class UserResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for user.
    
    Returned by API endpoints when fetching or updating users.
    Includes all user details and role information.
    
    Attributes:
        id: User ID
        display_name: Display name shown in UI
        username: Username for login
        telegram_id: Telegram ID for linking
        role: User role (admin, teacher, viewer)
        last_login_at: Last login timestamp
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="User ID")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    username: Optional[str] = Field(None, max_length=255, description="Username for login")
    telegram_id: Optional[int] = Field(None, description="Telegram ID")
    role: UserRole = Field(..., description="User role")
    is_platform_admin: bool = Field(False, description="Whether user is an allowlisted platform operator")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")


class UserListResponse(BaseResponse):
    """Response schema for user list.
    
    Note: This is deprecated in favor of PaginatedResponse[UserResponse].
    Kept for backward compatibility.
    
    Attributes:
        users: List of users
    """
    users: list[UserResponse] = Field(..., description="List of users")


class UserRoleUpdateRequest(BaseRequest):
    """Request schema for updating user role.
    
    Used to change a user's role within the system.
    
    Attributes:
        role: New user role (admin, teacher, or viewer)
    
    Validation:
        - role must be one of: admin, teacher, viewer
    """
    role: UserRole = Field(..., description="New user role")


class UserUpdateRequest(BaseRequest):
    """Request schema for updating user information.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        display_name: New display name (1-255 chars)
        username: New username (1-255 chars)
        role: New user role
    
    Validation:
        - If provided, display_name must be non-empty and <= 255 chars
        - If provided, username must be non-empty and <= 255 chars
        - If provided, role must be one of: admin, teacher, viewer
    """
    display_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Display name")
    username: Optional[str] = Field(None, min_length=1, max_length=255, description="Username")
    role: Optional[UserRole] = Field(None, description="User role")

    @field_validator('display_name', 'username')
    @classmethod
    def validate_string_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and trim string fields.
        
        Args:
            v: String to validate
            
        Returns:
            Trimmed string or None
            
        Raises:
            ValueError: If string is empty after trimming
        """
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only")
        return trimmed


__all__ = [
    'UserRole',
    'UserResponse',
    'UserListResponse',
    'UserRoleUpdateRequest',
    'UserUpdateRequest',
]
