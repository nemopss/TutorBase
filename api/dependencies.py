"""FastAPI dependency injection for authentication and database sessions.

This module provides dependency functions for FastAPI endpoints to handle:
- Database session management with automatic commit/rollback
- User authentication via JWT tokens (cached for 300s)
- Role-based access control (RBAC)
- Multi-tenancy context resolution with security validation

Key components:
    - get_session: Database session dependency with transaction management
    - get_current_user: Extract and validate user from JWT token (cached)
    - get_current_tenant: Resolve tenant context with security checks
    - require_roles: Role-based access control decorator
    - CurrentTenant: Dataclass for tenant context information

Caching strategy:
    - User lookups cached for 300s (balance security and performance)
    - Cache includes user role for permission checks
    - Cache invalidated on user updates (role changes, etc.)
    - Critical for performance as user lookup happens on every request

Security features:
    - JWT token validation for all authenticated endpoints
    - Tenant isolation enforcement for regular users
    - Super admin tenant switching with validation
    - Tenant activity status checks
    - Token tenant_id mismatch detection

Usage in endpoints:
    @router.get("/items")
    async def get_items(
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
        current_tenant: CurrentTenant = Depends(get_current_tenant)
    ):
        # Endpoint logic with authenticated user and tenant context
        pass
"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import async_session
from api.security import TokenType, TokenVerificationError, decode_token
from database import crud
from utils.cache import cached

_http_bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide database session with automatic transaction management.

    Creates async database session for request lifecycle. Automatically commits
    on success, rolls back on exception, and ensures session is closed.

    Yields:
        AsyncSession for database operations

    Raises:
        Exception: Re-raises any exception after rollback
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@cached(ttl=300, key_prefix="users")
async def _get_user_cached(session: AsyncSession, user_id: int):
    """Get user by ID with caching.
    
    Cached for 300 seconds (5 minutes) to reduce database load on authentication.
    This is called on EVERY authenticated request, so caching is critical.
    
    Args:
        session: Database session
        user_id: User ID to fetch
        
    Returns:
        User model or None
    """
    return await crud.get_user(session, user_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    session: AsyncSession = Depends(get_session),
):
    """Extract and validate current user from JWT token.

    Validates Bearer token, decodes JWT payload, and loads user from database.
    Used as dependency for all authenticated endpoints.
    
    User data is cached for 300 seconds to improve performance, as this function
    is called on every authenticated request.

    Args:
        credentials: HTTP Bearer token from Authorization header
        session: Database session dependency

    Returns:
        User model for authenticated user

    Raises:
        HTTPException: 401 if credentials missing, invalid, or user not found
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Use cached user lookup (critical for performance)
    user = await _get_user_cached(session, int(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    """Create role-based access control dependency.

    Factory function that returns dependency checker for specified roles.
    Used to restrict endpoints to users with specific roles.

    Args:
        *roles: Required role names (e.g., "admin", "teacher")

    Returns:
        Async dependency function that validates user role

    Raises:
        HTTPException: 403 if user doesn't have required role

    Example:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_roles("admin"))):
            pass
    """
    async def _checker(user=Depends(get_current_user)):
        """Validate user has required role.

        Args:
            user: Authenticated user from get_current_user

        Returns:
            User if role check passes

        Raises:
            HTTPException: 403 if user lacks required role
        """
        if roles and user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker


#: Pre-configured dependency for admin-only endpoints
admin_required = require_roles("admin")

#: Pre-configured dependency for admin or teacher endpoints
admin_or_teacher_required = require_roles("admin", "teacher")


from dataclasses import dataclass
from database.models import User, Tenant

@dataclass
class CurrentTenant:
    """Tenant context information for multi-tenancy data isolation.

    Attributes:
        tenant_id: Current tenant ID for data filtering (None for super admin global context)
        is_super_admin: Whether user is super admin with cross-tenant access
        tenant: Loaded Tenant model (None for super admin global context)
    """

    tenant_id: int | None
    is_super_admin: bool
    tenant: Tenant | None = None


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentTenant:
    """Resolve tenant context with security validation for multi-tenancy.

    Determines tenant context based on user role and JWT token. Implements
    security checks to prevent tenant isolation bypass.

    Security logic:
        - Super admins: Can switch tenant context via JWT tenant_id or operate globally
        - Regular users: Must match JWT tenant_id with user.tenant_id
        - All users: Tenant must exist and be active

    Args:
        credentials: HTTP Bearer token for tenant context extraction
        user: Authenticated user from get_current_user dependency
        session: Database session dependency

    Returns:
        CurrentTenant with tenant_id, is_super_admin flag, and loaded tenant

    Raises:
        HTTPException: 403 if tenant not found, inactive, or token mismatch detected
    """
    is_super_admin = user.role == 'admin'
    
    # For super-admins, check if they're switching tenant context via JWT
    if is_super_admin and credentials:
        try:
            payload = decode_token(credentials.credentials, TokenType.ACCESS)
            jwt_tenant_id = payload.get("tenant_id")
            
            # Super-admin can switch to any active tenant or stay global (None)
            if jwt_tenant_id is not None:
                tenant = await session.get(Tenant, jwt_tenant_id)
                if not tenant:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, 
                        detail="Tenant not found"
                    )
                if not tenant.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, 
                        detail="Tenant is inactive"
                    )
                # When super-admin switches to specific tenant, treat as non-super-admin for data filtering
                # This ensures data is filtered by tenant_id
                return CurrentTenant(tenant_id=jwt_tenant_id, is_super_admin=False, tenant=tenant)
            
            # Super-admin in global context (no tenant filter)
            return CurrentTenant(tenant_id=None, is_super_admin=True, tenant=None)
            
        except TokenVerificationError:
            # Fallback to user's default tenant
            pass
    
    # For regular users, ensure JWT tenant_id matches user's tenant_id
    if not is_super_admin and credentials:
        try:
            payload = decode_token(credentials.credentials, TokenType.ACCESS)
            jwt_tenant_id = payload.get("tenant_id")
            
            if jwt_tenant_id != user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token tenant mismatch - possible security violation"
                )
        except TokenVerificationError:
            # Token is invalid, but get_current_user should have caught this
            pass
    
    # Load and validate user's tenant
    tenant = None
    if user.tenant_id is not None:
        tenant = await session.get(Tenant, user.tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User's tenant not found"
            )
        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User's tenant is inactive"
            )
    
    return CurrentTenant(tenant_id=user.tenant_id, is_super_admin=is_super_admin, tenant=tenant)

