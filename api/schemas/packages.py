"""Pydantic schemas for lesson package endpoints.

This module provides request/response models for lesson package operations,
including validation rules for package creation, updates, and responses.

Key components:
    - PackageCreateRequest: Schema for creating new packages
    - PackageUpdateRequest: Schema for updating existing packages
    - PackageResponse: Schema for package API responses
    - PackageProgressModel: Nested schema for package progress tracking

Validation rules:
    - Status must be one of: draft, active, completed, cancelled
    - Timezone must be valid IANA timezone
    - Total lessons must be positive (1-1000)
    - Title must be non-empty (1-255 chars)
    - Notes limited to 5000 chars
    - End date must be after start date
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, field_validator, model_validator

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin, TenantMixin
from api.schemas.validators import validate_status, validate_timezone, validate_date_range

# Valid package statuses
VALID_PACKAGE_STATUSES = ['draft', 'active', 'completed', 'cancelled']


class PackageProgressModel(BaseResponse):
    """Progress tracking for lesson packages.
    
    Tracks the number of lessons in different states within a package.
    
    Attributes:
        total: Total number of lessons in package
        completed: Number of completed lessons
        cancelled: Number of cancelled lessons
    """
    total: int = Field(ge=0, description="Total number of lessons")
    completed: int = Field(ge=0, description="Number of completed lessons")
    cancelled: int = Field(ge=0, description="Number of cancelled lessons")


class PackageResponse(BaseResponse, TimestampMixin, TenantMixin):
    """Response schema for lesson package.
    
    Returned by API endpoints when fetching or creating packages.
    Includes all package details and computed progress information.
    
    Attributes:
        id: Package ID
        learner_id: ID of learner this package belongs to
        learner_name: Display name of learner
        template_id: ID of template used (if any)
        title: Package title
        status: Current status (draft, active, completed, cancelled)
        start_date: Package start date
        end_date: Package end date
        timezone: Timezone for lesson scheduling
        notes: Teacher notes
        total_lessons: Total number of lessons
        progress: Progress tracking information
        price: Package price (calculated or manual)
        payment_status: Payment status (unpaid, partial, paid)
        created_at: Creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
        tenant_id: Tenant ID (from TenantMixin)
    """
    id: int = Field(..., description="Package ID")
    learner_id: int = Field(..., gt=0, description="Learner ID")
    learner_name: Optional[str] = Field(None, description="Learner display name")
    template_id: Optional[int] = Field(None, gt=0, description="Template ID if created from template")
    title: str = Field(..., min_length=1, max_length=255, description="Package title")
    status: str = Field(..., description="Package status")
    start_date: Optional[datetime] = Field(None, description="Package start date")
    end_date: Optional[datetime] = Field(None, description="Package end date")
    timezone: str = Field(..., description="Timezone for lesson scheduling")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    total_lessons: Optional[int] = Field(None, ge=0, description="Total number of lessons")
    progress: PackageProgressModel = Field(..., description="Progress tracking")
    price: Optional[float] = Field(None, description="Package price")
    payment_status: str = Field(default='unpaid', description="Payment status (unpaid, partial, paid)")
    total_paid: float = Field(default=0.0, description="Total amount paid for this package")


class PackageListResponse(BaseResponse):
    """Response schema for paginated package list.
    
    Note: This is deprecated in favor of PaginatedResponse[PackageResponse].
    Kept for backward compatibility.
    
    Attributes:
        total: Total number of packages
        items: List of packages
    """
    total: int = Field(ge=0, description="Total number of packages")
    items: list[PackageResponse] = Field(..., description="List of packages")


class PackageCreateRequest(BaseRequest):
    """Request schema for creating a new lesson package.
    
    Validates all required fields and business rules for package creation.
    
    Attributes:
        learner_id: ID of learner this package is for (required, must be positive)
        title: Package title (required, 1-255 chars)
        notes: Optional teacher notes (max 5000 chars)
        status: Package status (default: draft)
        template_id: Optional template to create from
        start_date: Optional start date
        timezone: Optional timezone (defaults to Europe/Moscow)
        total_lessons: Optional total lesson count (1-1000)
    
    Validation:
        - learner_id must be positive
        - title must be non-empty and <= 255 chars
        - status must be one of: draft, active, completed, cancelled
        - timezone must be valid IANA timezone
        - total_lessons must be between 1 and 1000
    """
    learner_id: int = Field(..., gt=0, description="ID of learner")
    title: str = Field(..., min_length=1, max_length=255, description="Package title")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    status: str = Field(default='draft', description="Package status")
    template_id: Optional[int] = Field(None, gt=0, description="Template ID to create from")
    start_date: Optional[datetime | str] = Field(None, description="Package start date")
    timezone: Optional[str] = Field(None, description="Timezone for scheduling")
    total_lessons: Optional[int] = Field(None, gt=0, le=1000, description="Total number of lessons")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: str) -> str:
        """Validate package status is one of allowed values.
        
        Args:
            v: Status value to validate
            
        Returns:
            Validated status
            
        Raises:
            ValueError: If status is not in allowed list
        """
        return validate_status(v, VALID_PACKAGE_STATUSES)

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

    @model_validator(mode='after')
    def validate_template_requires_start_date(self) -> 'PackageCreateRequest':
        """Validate that start_date is provided when using a template.
        
        Returns:
            Self with validated fields
            
        Raises:
            ValueError: If template_id is provided without start_date
        """
        if self.template_id is not None and self.start_date is None:
            raise ValueError("start_date is required when creating package from template")
        return self


class PackageUpdateRequest(BaseRequest):
    """Request schema for updating an existing lesson package.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        title: New package title (1-255 chars)
        status: New package status
        notes: New teacher notes (max 5000 chars)
        timezone: New timezone
        start_date: New start date
        end_date: New end date
        total_lessons: New total lesson count (1-1000)
    
    Validation:
        - If provided, title must be non-empty and <= 255 chars
        - If provided, status must be one of: draft, active, completed, cancelled
        - If provided, timezone must be valid IANA timezone
        - If provided, total_lessons must be between 1 and 1000
        - If both dates provided, end_date must be after start_date
    """
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Package title")
    status: Optional[str] = Field(None, description="Package status")
    notes: Optional[str] = Field(None, max_length=5000, description="Teacher notes")
    timezone: Optional[str] = Field(None, description="Timezone for scheduling")
    start_date: Optional[datetime] = Field(None, description="Package start date")
    end_date: Optional[datetime] = Field(None, description="Package end date")
    total_lessons: Optional[int] = Field(None, gt=0, le=1000, description="Total number of lessons")

    @field_validator('status')
    @classmethod
    def validate_status_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate package status is one of allowed values.
        
        Args:
            v: Status value to validate
            
        Returns:
            Validated status or None
            
        Raises:
            ValueError: If status is not in allowed list
        """
        if v is None:
            return v
        return validate_status(v, VALID_PACKAGE_STATUSES)

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

    @model_validator(mode='after')
    def validate_date_range_fields(self) -> 'PackageUpdateRequest':
        """Validate that end_date is after start_date if both provided.
        
        Returns:
            Self with validated dates
            
        Raises:
            ValueError: If end_date is before or equal to start_date
        """
        if self.start_date is not None and self.end_date is not None:
            validate_date_range(self.start_date, self.end_date)
        return self


__all__ = [
    'PackageProgressModel',
    'PackageResponse',
    'PackageListResponse',
    'PackageCreateRequest',
    'PackageUpdateRequest',
    'VALID_PACKAGE_STATUSES',
]

