"""Base Pydantic models and mixins for common fields.

This module provides reusable base classes and mixins for API schemas,
reducing duplication and ensuring consistency across all models.

Key components:
    - TimestampMixin: Common timestamp fields (created_at, updated_at)
    - TenantMixin: Tenant isolation field (tenant_id)
    - BaseResponse: Base class for all response models
    - BaseRequest: Base class for all request models

Usage:
    class PackageResponse(BaseResponse, TimestampMixin):
        id: int
        title: str
        # Automatically includes created_at, updated_at from mixin
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields.
    
    Provides created_at and updated_at fields that are common
    across most database entities.
    
    Attributes:
        created_at: When the entity was created
        updated_at: When the entity was last updated
    
    Note:
        Fields are optional to support manual response construction.
        When using from_attributes=True with ORM models, these will be populated automatically.
    """
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class TenantMixin(BaseModel):
    """Mixin for models with tenant isolation.
    
    Provides tenant_id field for multi-tenancy support.
    
    Attributes:
        tenant_id: ID of the tenant this entity belongs to
    """
    tenant_id: Optional[int] = Field(None, description="Tenant ID for multi-tenancy")


class BaseResponse(BaseModel):
    """Base class for all API response models.
    
    Configures Pydantic to work with SQLAlchemy ORM models
    and provides common response behavior.
    
    Configuration:
        - from_attributes: Allow creation from ORM models
        - json_encoders: Custom JSON encoding for datetime
        - populate_by_name: Allow field population by name or alias
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class BaseRequest(BaseModel):
    """Base class for all API request models.
    
    Provides common request validation behavior and configuration.
    
    Configuration:
        - str_strip_whitespace: Automatically strip whitespace from strings
        - validate_assignment: Validate on attribute assignment
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )


__all__ = [
    'TimestampMixin',
    'TenantMixin',
    'BaseResponse',
    'BaseRequest',
]
