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
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import async_session
from api.security import TokenType, TokenVerificationError, decode_token
from config import config
from database import crud
from services import tenant_access_service
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
    
    Cached for 300s (5 minutes) to improve performance on authenticated requests.
    Cache returns dict, so we need to handle both User model and dict.
    
    Args:
        session: Database session
        user_id: User ID to fetch
        
    Returns:
        User model or dict with user data
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
    
    # Handle both User model and dict (from cache)
    if isinstance(user, dict):
        # Cache returned dict, convert to User model for compatibility
        from database.models import User
        user_obj = User()
        for key, value in user.items():
            if not key.startswith('_'):
                setattr(user_obj, key, value)
        return user_obj
    
    return user


def is_platform_admin(user) -> bool:
    """Return whether the user is an allowlisted platform operator."""
    telegram_id = getattr(user, "telegram_id", None)
    if telegram_id is None:
        return False
    try:
        return int(telegram_id) in config.ADMINS
    except (TypeError, ValueError):
        return False


def _has_required_role(user, roles: tuple[str, ...]) -> bool:
    if not roles:
        return True
    if "admin" in roles and is_platform_admin(user):
        return True
    regular_roles = {role for role in roles if role != "admin"}
    return getattr(user, "role", None) in regular_roles


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
        if not _has_required_role(user, roles):
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
    access_status: str | None = None
    access_mode: str | None = None
    access_until: datetime | None = None
    grace_until: datetime | None = None
    access_reason: str | None = None
    bypass_access_restrictions: bool = False


async def _resolve_tenant_access(
    session: AsyncSession,
    tenant: Tenant,
    *,
    bypass_restrictions: bool = False,
) -> tenant_access_service.TenantAccessSnapshot:
    snapshot = await tenant_access_service.get_access_snapshot(session, tenant.id)
    if bypass_restrictions or not snapshot.is_blocked:
        return snapshot

    if snapshot.status == tenant_access_service.ACCESS_STATUS_SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_ACCESS_SUSPENDED",
                "message": "Tenant access is suspended",
                "tenant_id": tenant.id,
                "status": snapshot.status,
            },
        )

    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "TENANT_ACCESS_EXPIRED",
            "message": "Tenant access has expired",
            "tenant_id": tenant.id,
            "status": snapshot.status,
            "access_until": snapshot.access_until.isoformat() if snapshot.access_until else None,
            "grace_until": snapshot.grace_until.isoformat() if snapshot.grace_until else None,
        },
    )


def _tenant_context_from_access(
    tenant: Tenant,
    *,
    is_super_admin: bool,
    snapshot: tenant_access_service.TenantAccessSnapshot,
    bypass_restrictions: bool = False,
) -> CurrentTenant:
    return CurrentTenant(
        tenant_id=tenant.id,
        is_super_admin=is_super_admin,
        tenant=tenant,
        access_status=snapshot.status,
        access_mode=snapshot.mode,
        access_until=snapshot.access_until,
        grace_until=snapshot.grace_until,
        access_reason=snapshot.reason,
        bypass_access_restrictions=bypass_restrictions,
    )


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
    is_super_admin = is_platform_admin(user)
    
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
                snapshot = await _resolve_tenant_access(session, tenant, bypass_restrictions=True)
                # When super-admin switches to specific tenant, treat as non-super-admin for data filtering
                # This ensures data is filtered by tenant_id
                return _tenant_context_from_access(
                    tenant,
                    is_super_admin=False,
                    snapshot=snapshot,
                    bypass_restrictions=True,
                )
            
            # Super-admin in global context (no tenant filter)
            return CurrentTenant(tenant_id=None, is_super_admin=True, tenant=None, bypass_access_restrictions=True)
            
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
        snapshot = await _resolve_tenant_access(session, tenant, bypass_restrictions=False)
        return _tenant_context_from_access(
            tenant,
            is_super_admin=is_super_admin,
            snapshot=snapshot,
            bypass_restrictions=False,
        )
    
    return CurrentTenant(tenant_id=user.tenant_id, is_super_admin=is_super_admin, tenant=tenant)
