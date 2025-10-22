"""Pagination schemas for list endpoints.

This module provides standardized pagination request/response models
for all list endpoints in the API.

Key components:
    - PaginationParams: Query parameters for pagination
    - PaginatedResponse: Standardized paginated response wrapper

Usage:
    # In route handler
    @router.get("/items", response_model=PaginatedResponse[ItemResponse])
    async def list_items(
        pagination: PaginationParams = Depends(),
        ...
    ):
        items, total = await service.list_items(
            limit=pagination.limit,
            offset=pagination.offset,
        )
        return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)
"""
from typing import Generic, TypeVar, List

from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Query parameters for pagination.
    
    Provides limit and offset parameters with sensible defaults
    and validation rules.
    
    Attributes:
        limit: Maximum number of items to return (1-100, default 50)
        offset: Number of items to skip (>=0, default 0)
    
    Example:
        >>> params = PaginationParams(limit=20, offset=40)
        >>> # Returns items 41-60
    """
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of items to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response wrapper.
    
    Wraps list results with pagination metadata for consistent
    API responses across all list endpoints.
    
    Attributes:
        items: List of items for current page
        total: Total number of items (across all pages)
        limit: Maximum items per page (from request)
        offset: Number of items skipped (from request)
        has_more: Whether there are more items after this page
    
    Example:
        >>> response = PaginatedResponse.create(
        ...     items=[item1, item2],
        ...     total=100,
        ...     limit=50,
        ...     offset=0
        ... )
        >>> response.has_more  # True (50 more items available)
    """
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., ge=0, description="Total number of items across all pages")
    limit: int = Field(..., ge=1, description="Maximum items per page")
    offset: int = Field(..., ge=0, description="Number of items skipped")
    has_more: bool = Field(..., description="Whether more items are available")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        limit: int,
        offset: int,
    ) -> 'PaginatedResponse[T]':
        """Create paginated response with automatic has_more calculation.
        
        Factory method that calculates has_more flag based on
        current page position and total count.
        
        Args:
            items: List of items for current page
            total: Total number of items
            limit: Maximum items per page
            offset: Number of items skipped
            
        Returns:
            PaginatedResponse with all fields populated
            
        Example:
            >>> PaginatedResponse.create(
            ...     items=[1, 2, 3],
            ...     total=10,
            ...     limit=3,
            ...     offset=0
            ... )
            PaginatedResponse(items=[1,2,3], total=10, has_more=True)
        """
        has_more = (offset + len(items)) < total
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )


__all__ = [
    'PaginationParams',
    'PaginatedResponse',
]
