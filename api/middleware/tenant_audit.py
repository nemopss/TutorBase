"""
Tenant audit middleware for SaaS security.
Logs all tenant-related operations for security monitoring.
"""
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("tenant_audit")


class TenantAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to audit tenant operations for SaaS security.
    Logs tenant switches, cross-tenant access attempts, and suspicious activity.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract tenant context from request if available
        tenant_id = None
        user_id = None
        is_super_admin = False
        
        # Try to get user info from the request state (set by dependencies)
        if hasattr(request.state, 'current_tenant'):
            current_tenant = request.state.current_tenant
            tenant_id = current_tenant.tenant_id
            is_super_admin = current_tenant.is_super_admin
        
        if hasattr(request.state, 'current_user'):
            user_id = request.state.current_user.id
        
        # Log tenant switch operations
        if request.url.path == "/api/v1/auth/switch-tenant" and request.method == "POST":
            logger.info(
                "Tenant switch attempt",
                extra={
                    "user_id": user_id,
                    "is_super_admin": is_super_admin,
                    "ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }
            )
        
        response = await call_next(request)
        
        # Log suspicious activity (4xx errors on tenant operations)
        if response.status_code in [403, 404] and "/api/v1/" in request.url.path:
            logger.warning(
                "Potential tenant isolation violation",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "is_super_admin": is_super_admin,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "ip": request.client.host if request.client else None,
                    "processing_time": time.time() - start_time,
                }
            )
        
        return response