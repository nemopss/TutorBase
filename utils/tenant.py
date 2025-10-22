"""Tenant resolution utilities for multi-tenancy support.

This module provides helper functions for resolving tenant_id in CRUD operations,
eliminating code duplication and ensuring consistent tenant isolation logic.

Key components:
    - resolve_tenant_id: Centralized tenant_id resolution for CRUD operations
    - validate_tenant_access: Check if user has access to specific tenant

Business rules:
    - Super admins can specify any tenant_id or operate globally (None)
    - Regular users must use their assigned tenant_id
    - Operations requiring tenant context must have non-None tenant_id

Usage:
    # In CRUD methods
    final_tenant_id = resolve_tenant_id(current_tenant, requested_tenant_id)
    
    # Create entity with resolved tenant
    entity = Model(tenant_id=final_tenant_id, ...)
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from api.dependencies import CurrentTenant


def resolve_tenant_id(
    current_tenant: "CurrentTenant",
    requested_tenant_id: Optional[int] = None,
    require_tenant: bool = True,
) -> Optional[int]:
    """Resolve tenant_id for database operations with security validation.
    
    Implements multi-tenancy security rules:
    - Super admins can specify any tenant_id or None (global operations)
    - Regular users must use their assigned tenant_id
    - Attempting to access different tenant raises ValueError
    
    Args:
        current_tenant: Current tenant context from dependency injection
        requested_tenant_id: Optional tenant_id from request (super admin only)
        require_tenant: If True, raises error when result is None
        
    Returns:
        Resolved tenant_id to use for database operation
        
    Raises:
        ValueError: If regular user tries to specify different tenant_id
        ValueError: If require_tenant=True and result would be None
        
    Examples:
        # Super admin specifying tenant
        >>> resolve_tenant_id(super_admin_context, requested_tenant_id=5)
        5
        
        # Super admin without specification (global operation)
        >>> resolve_tenant_id(super_admin_context, requested_tenant_id=None)
        None
        
        # Regular user (uses their tenant)
        >>> resolve_tenant_id(regular_user_context, requested_tenant_id=None)
        3
        
        # Regular user trying to access different tenant (ERROR)
        >>> resolve_tenant_id(regular_user_context, requested_tenant_id=5)
        ValueError: Only super admins can specify tenant_id
    """
    # Super admin can specify any tenant or operate globally
    if current_tenant.is_super_admin:
        if requested_tenant_id is not None:
            # Super admin explicitly specified tenant
            return requested_tenant_id
        # Super admin without specification - use their context (may be None for global)
        result = current_tenant.tenant_id
    else:
        # Regular user - must use their assigned tenant
        if requested_tenant_id is not None and requested_tenant_id != current_tenant.tenant_id:
            raise ValueError(
                f"Only super admins can specify tenant_id. "
                f"User tenant: {current_tenant.tenant_id}, requested: {requested_tenant_id}"
            )
        result = current_tenant.tenant_id
    
    # Validate tenant requirement
    if require_tenant and result is None:
        raise ValueError(
            "Tenant context required for this operation. "
            "Super admins must specify tenant_id or switch to tenant context."
        )
    
    return result


def validate_tenant_access(
    current_tenant: "CurrentTenant",
    entity_tenant_id: Optional[int],
    operation: str = "access",
) -> None:
    """Validate that current user has access to entity's tenant.
    
    Ensures data isolation by checking that user can access the entity.
    Super admins can access any tenant, regular users only their own.
    
    Args:
        current_tenant: Current tenant context
        entity_tenant_id: Tenant ID of the entity being accessed
        operation: Operation name for error message (e.g., "update", "delete")
        
    Raises:
        ValueError: If user doesn't have access to entity's tenant
        
    Examples:
        # Regular user accessing their own tenant's entity
        >>> validate_tenant_access(user_context, entity_tenant_id=3, operation="update")
        # No error
        
        # Regular user trying to access different tenant (ERROR)
        >>> validate_tenant_access(user_context, entity_tenant_id=5, operation="delete")
        ValueError: Cannot delete entity - does not belong to tenant 3
        
        # Super admin can access any tenant
        >>> validate_tenant_access(super_admin_context, entity_tenant_id=5)
        # No error
    """
    # Super admins can access any tenant
    if current_tenant.is_super_admin:
        return
    
    # Regular users can only access their own tenant
    if entity_tenant_id != current_tenant.tenant_id:
        raise ValueError(
            f"Cannot {operation} entity - does not belong to tenant {current_tenant.tenant_id}. "
            f"Entity tenant: {entity_tenant_id}"
        )


def get_tenant_filter(current_tenant: "CurrentTenant") -> Optional[int]:
    """Get tenant_id for filtering queries.
    
    Returns tenant_id to use in WHERE clauses for data isolation.
    Super admins in global context return None (no filter).
    
    Args:
        current_tenant: Current tenant context
        
    Returns:
        Tenant ID for filtering, or None for global queries
        
    Examples:
        # Regular user - always filter by their tenant
        >>> get_tenant_filter(user_context)
        3
        
        # Super admin in tenant context - filter by that tenant
        >>> get_tenant_filter(super_admin_in_tenant_context)
        5
        
        # Super admin in global context - no filter
        >>> get_tenant_filter(super_admin_global_context)
        None
    """
    return current_tenant.tenant_id


def require_tenant_context(current_tenant: "CurrentTenant") -> int:
    """Require non-None tenant context, raise error otherwise.
    
    Convenience function for operations that cannot work in global context.
    
    Args:
        current_tenant: Current tenant context
        
    Returns:
        Non-None tenant_id
        
    Raises:
        ValueError: If tenant_id is None
        
    Example:
        >>> tenant_id = require_tenant_context(current_tenant)
        >>> # Use tenant_id knowing it's not None
    """
    if current_tenant.tenant_id is None:
        raise ValueError(
            "This operation requires tenant context. "
            "Super admins must specify tenant_id or switch to tenant context."
        )
    return current_tenant.tenant_id


__all__ = [
    'resolve_tenant_id',
    'validate_tenant_access',
    'get_tenant_filter',
    'require_tenant_context',
]
