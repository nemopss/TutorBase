from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import async_session
from api.security import TokenType, TokenVerificationError, decode_token
from database import crud

_http_bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    session: AsyncSession = Depends(get_session),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await crud.get_user(session, int(subject))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    async def _checker(user=Depends(get_current_user)):
        if roles and user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker


admin_required = require_roles("admin")
admin_or_teacher_required = require_roles("admin", "teacher")


from dataclasses import dataclass
from database.models import User, Tenant

@dataclass
class CurrentTenant:
    tenant_id: int | None
    is_super_admin: bool
    tenant: Tenant | None = None


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentTenant:
    """
    Enhanced tenant context with JWT validation and tenant activity check.
    For SaaS security, we validate JWT tenant_id against user's actual tenant.
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

