"""Service for managing tenants in multi-tenancy system.

This module contains business logic for tenant management in the multi-tenancy
architecture. Tenants represent separate organizations or tutoring businesses
that share the same application infrastructure but have isolated data.

Key components:
    - create_tenant: Create a new tenant organization
    - get_tenant: Retrieve tenant by ID
    - list_tenants: Get paginated list of all tenants
    - update_tenant: Update tenant parameters
    - delete_tenant: Delete tenant and all associated data

Multi-tenancy architecture:
    - Each tenant has isolated data (learners, packages, lessons, users)
    - Tenant identified by unique slug and ID
    - All data operations filtered by tenant_id for isolation
    - Super admins can manage multiple tenants
    - Regular users belong to single tenant

Security implications:
    - Tenant isolation is critical for data security
    - All service operations must respect tenant boundaries
    - CurrentTenant context ensures proper data isolation
    - Deleting tenant removes all associated data (use with caution)
    - Tenant slug used for subdomain/routing in multi-tenant deployments

Relationships:
    - Users belong to tenants (tenant_id foreign key)
    - All business entities (learners, packages, lessons) belong to tenants
    - Tenant deactivation (is_active=False) prevents access
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database.models import Tenant
from services.exceptions import NotFoundError


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    contact_email: Optional[str] = None,
    is_active: bool = True,
) -> Tenant:
    """Create a new tenant organization.

    Creates a new tenant with isolated data space. Slug must be unique and is
    used for tenant identification in routing/subdomains.

    Args:
        session: Async database session
        name: Display name for the tenant organization
        slug: Unique identifier slug (used in URLs, must be unique)
        contact_email: Contact email for tenant admin (optional)
        is_active: Whether tenant is active (default True)

    Returns:
        Created Tenant model

    Raises:
        IntegrityError: If slug already exists (handled by database layer)
    """
    return await crud.create_tenant(
        session,
        name=name,
        slug=slug,
        contact_email=contact_email,
        is_active=is_active,
    )


async def get_tenant(session: AsyncSession, tenant_id: int) -> Tenant:
    """Retrieve tenant by ID.

    Args:
        session: Async database session
        tenant_id: Tenant ID to retrieve

    Returns:
        Tenant model

    Raises:
        NotFoundError: If tenant with specified ID is not found
    """
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return tenant


async def list_tenants(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Tenant], int]:
    """Get paginated list of all tenants.

    Retrieves all tenants in the system with pagination. Typically used by
    super admins for tenant management.

    Args:
        session: Async database session
        limit: Maximum number of tenants to return (default 100)
        offset: Offset for pagination (default 0)

    Returns:
        Tuple of (list of Tenant models, total count)
    """
    return await crud.list_tenants(session, limit=limit, offset=offset)


async def update_tenant(
    session: AsyncSession,
    tenant_id: int,
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    contact_email: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Tenant:
    """Update tenant parameters.

    Updates specified tenant fields. All parameters are optional - only provided
    values are updated. Setting is_active=False effectively disables the tenant
    and prevents user access.

    Args:
        session: Async database session
        tenant_id: Tenant ID to update
        name: New display name (optional)
        slug: New unique slug (optional, must be unique)
        contact_email: New contact email (optional)
        is_active: New active status (optional, False disables tenant)

    Returns:
        Updated Tenant model

    Raises:
        NotFoundError: If tenant with specified ID is not found
        IntegrityError: If new slug conflicts with existing tenant
    """
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return await crud.update_tenant(
        session,
        tenant,
        name=name,
        slug=slug,
        contact_email=contact_email,
        is_active=is_active,
    )


async def delete_tenant(session: AsyncSession, tenant_id: int) -> None:
    """Delete tenant and all associated data.

    Permanently deletes tenant and all related data (users, learners, packages,
    lessons, reminders). This operation is irreversible and should be used with
    extreme caution. Consider deactivating tenant (is_active=False) instead.

    Security warning: This will delete ALL data for the tenant including all
    users, learners, lesson packages, and historical data.

    Args:
        session: Async database session
        tenant_id: Tenant ID to delete

    Raises:
        NotFoundError: If tenant with specified ID is not found
    """
    tenant = await crud.get_tenant(session, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    await crud.delete_tenant(session, tenant)
