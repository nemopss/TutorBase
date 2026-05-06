"""
Slow query logging for performance monitoring.
Logs queries that exceed performance thresholds with tenant context.
"""
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from api.log_sanitizer import redact_query_params

logger = logging.getLogger("slow_query")


class SlowQueryLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log slow queries with tenant context.
    Helps identify performance bottlenecks and optimization opportunities.
    """
    
    def __init__(self, app, threshold_seconds: float = 0.1):
        """
        Initialize slow query logger.
        
        Args:
            app: FastAPI application
            threshold_seconds: Queries slower than this will be logged (default: 100ms)
        """
        super().__init__(app)
        self.threshold = threshold_seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract context
        tenant_id = None
        user_id = None
        is_super_admin = False
        
        if hasattr(request.state, 'current_tenant'):
            current_tenant = request.state.current_tenant
            tenant_id = current_tenant.tenant_id
            is_super_admin = current_tenant.is_super_admin
        
        if hasattr(request.state, 'current_user'):
            user_id = request.state.current_user.id
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Log slow queries
        if duration > self.threshold:
            # Determine severity based on duration
            if duration > 1.0:
                log_level = logging.ERROR
                severity = "CRITICAL"
            elif duration > 0.5:
                log_level = logging.WARNING
                severity = "HIGH"
            else:
                log_level = logging.INFO
                severity = "MEDIUM"
            
            logger.log(
                log_level,
                f"Slow query detected [{severity}]",
                extra={
                    "severity": severity,
                    "duration_ms": round(duration * 1000, 2),
                    "threshold_ms": round(self.threshold * 1000, 2),
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "is_super_admin": is_super_admin,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": redact_query_params(request.query_params),
                    "status_code": response.status_code,
                    "client_ip": request.client.host if request.client else None,
                }
            )
            
            # Add performance warning header for debugging
            response.headers["X-Query-Time-Ms"] = str(round(duration * 1000, 2))
            if duration > self.threshold:
                response.headers["X-Performance-Warning"] = "slow-query"
        
        return response


def create_slow_query_logger(threshold_seconds: float = 0.1) -> SlowQueryLoggerMiddleware:
    """
    Factory function to create slow query logger middleware.
    
    Args:
        threshold_seconds: Queries slower than this will be logged (default: 100ms)
    
    Returns:
        Configured SlowQueryLoggerMiddleware instance
    """
    def middleware_factory(app):
        return SlowQueryLoggerMiddleware(app, threshold_seconds=threshold_seconds)
    
    return middleware_factory
