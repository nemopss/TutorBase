"""Pydantic schemas for lesson package template endpoints.

This module provides request/response models for template operations,
including validation rules for template creation, updates, and responses.

Key components:
    - TemplateCreateRequest: Schema for creating new templates
    - TemplateUpdateRequest: Schema for updating existing templates
    - TemplateResponse: Schema for template API responses

Validation rules:
    - Name must be non-empty and unique (1-255 chars)
    - Description limited to 5000 chars
    - Lesson count must be positive (1-1000)
    - Duration days must be positive (1-3650, i.e., up to 10 years)
    - Timezone must be valid IANA timezone
    - Default config must be valid JSON dict
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from pydantic import Field, field_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin
from api.schemas.validators import validate_timezone


class TemplateResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for lesson package template.
    
    Returned by API endpoints when fetching or creating templates.
    Includes all template configuration and metadata.
    
    Attributes:
        id: Template ID
        name: Unique template name
        description: Template description
        lesson_count: Default number of lessons
        duration_days: Default package duration in days
        timezone: Default timezone for scheduling
        default_config: JSON configuration for template
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="Template ID")
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, max_length=5000, description="Template description")
    lesson_count: Optional[int] = Field(None, gt=0, le=1000, description="Default lesson count")
    duration_days: Optional[int] = Field(None, gt=0, le=3650, description="Default duration in days")
    timezone: str = Field(..., description="Default timezone")
    default_config: Dict[str, Any] = Field(default_factory=dict, description="Template configuration")


class TemplateListResponse(BaseResponse):
    """Response schema for template list.
    
    Note: This is deprecated in favor of PaginatedResponse[TemplateResponse].
    Kept for backward compatibility.
    
    Attributes:
        total: Total number of templates
        items: List of templates
    """
    total: int = Field(ge=0, description="Total number of templates")
    items: list[TemplateResponse] = Field(..., description="List of templates")


class TemplateCreateRequest(BaseRequest):
    """Request schema for creating a new lesson package template.
    
    Validates all required fields and business rules for template creation.
    
    Attributes:
        name: Unique template name (required, 1-255 chars)
        description: Optional description (max 5000 chars)
        lesson_count: Default lesson count (1-1000)
        duration_days: Default duration in days (1-3650)
        timezone: Default timezone (default: Europe/Moscow)
        default_config: JSON configuration dict
    
    Validation:
        - name must be non-empty and <= 255 chars
        - description max 5000 chars
        - lesson_count must be between 1 and 1000
        - duration_days must be between 1 and 3650 (10 years)
        - timezone must be valid IANA timezone
    """
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, max_length=5000, description="Template description")
    lesson_count: Optional[int] = Field(None, gt=0, le=1000, description="Default lesson count")
    duration_days: Optional[int] = Field(None, gt=0, le=3650, description="Default duration in days")
    timezone: str = Field(default="Europe/Moscow", description="Default timezone")
    default_config: Dict[str, Any] = Field(default_factory=dict, description="Template configuration")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and trim template name.
        
        Args:
            v: Template name to validate
            
        Returns:
            Trimmed template name
            
        Raises:
            ValueError: If name is empty after trimming
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Template name cannot be empty or whitespace only")
        return trimmed

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, v: str) -> str:
        """Validate timezone is a valid IANA timezone.
        
        Args:
            v: Timezone string to validate
            
        Returns:
            Validated timezone
            
        Raises:
            ValueError: If timezone is invalid
        """
        return validate_timezone(v)


class TemplateUpdateRequest(BaseRequest):
    """Request schema for updating an existing lesson package template.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        name: New template name (1-255 chars)
        description: New description (max 5000 chars)
        lesson_count: New default lesson count (1-1000)
        duration_days: New default duration in days (1-3650)
        timezone: New default timezone
        default_config: New configuration dict
    
    Validation:
        - If provided, name must be non-empty and <= 255 chars
        - If provided, description max 5000 chars
        - If provided, lesson_count must be between 1 and 1000
        - If provided, duration_days must be between 1 and 3650
        - If provided, timezone must be valid IANA timezone
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, max_length=5000, description="Template description")
    lesson_count: Optional[int] = Field(None, gt=0, le=1000, description="Default lesson count")
    duration_days: Optional[int] = Field(None, gt=0, le=3650, description="Default duration in days")
    timezone: Optional[str] = Field(None, description="Default timezone")
    default_config: Optional[Dict[str, Any]] = Field(None, description="Template configuration")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and trim template name.
        
        Args:
            v: Template name to validate
            
        Returns:
            Trimmed template name or None
            
        Raises:
            ValueError: If name is empty after trimming
        """
        if v is None:
            return v
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Template name cannot be empty or whitespace only")
        return trimmed

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate timezone is a valid IANA timezone.
        
        Args:
            v: Timezone string to validate
            
        Returns:
            Validated timezone or None
            
        Raises:
            ValueError: If timezone is invalid
        """
        if v is None:
            return v
        return validate_timezone(v)


__all__ = [
    'TemplateResponse',
    'TemplateListResponse',
    'TemplateCreateRequest',
    'TemplateUpdateRequest',
]
