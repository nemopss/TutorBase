"""
Tenant metrics collection middleware for SaaS monitoring.
Tracks tenant operations, performance, and usage patterns.
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("tenant_metrics")


class TenantMetricsCollector:
    """
    Collects and stores tenant metrics in memory.
    In production, this should be replaced with a proper metrics backend (Prometheus, DataDog, etc.)
    """
    
    def __init__(self):
        # Metrics storage (in-memory for now)
        self.query_times: Dict[int, list] = defaultdict(list)
        self.request_counts: Dict[int, int] = defaultdict(int)
        self.cross_tenant_attempts: Dict[int, int] = defaultdict(int)
        self.tenant_switches: list = []
        self.error_counts: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    
    def record_query_time(self, tenant_id: int | None, duration: float):
        """Record query execution time for a tenant."""
        if tenant_id is not None:
            self.query_times[tenant_id].append(duration)
    
    def record_request(self, tenant_id: int | None):
        """Record a request for a tenant."""
        if tenant_id is not None:
            self.request_counts[tenant_id] += 1
    
    def record_cross_tenant_attempt(self, tenant_id: int | None):
        """Record a cross-tenant access attempt (security violation)."""
        if tenant_id is not None:
            self.cross_tenant_attempts[tenant_id] += 1
    
    def record_tenant_switch(self, user_id: int, from_tenant: int | None, to_tenant: int | None):
        """Record a tenant context switch."""
        self.tenant_switches.append({
            "timestamp": datetime.now(timezone.utc),
            "user_id": user_id,
            "from_tenant": from_tenant,
            "to_tenant": to_tenant,
        })
    
    def record_error(self, tenant_id: int | None, status_code: int):
        """Record an error for a tenant."""
        if tenant_id is not None:
            self.error_counts[tenant_id][status_code] += 1
    
    def get_tenant_stats(self, tenant_id: int) -> dict:
        """Get statistics for a specific tenant."""
        query_times = self.query_times.get(tenant_id, [])
        
        return {
            "tenant_id": tenant_id,
            "total_requests": self.request_counts.get(tenant_id, 0),
            "cross_tenant_attempts": self.cross_tenant_attempts.get(tenant_id, 0),
            "avg_query_time": sum(query_times) / len(query_times) if query_times else 0,
            "max_query_time": max(query_times) if query_times else 0,
            "min_query_time": min(query_times) if query_times else 0,
            "total_queries": len(query_times),
            "errors": dict(self.error_counts.get(tenant_id, {})),
        }
    
    def get_all_tenant_stats(self) -> list:
        """Get statistics for all tenants."""
        tenant_ids = set(self.request_counts.keys()) | set(self.query_times.keys())
        return [self.get_tenant_stats(tid) for tid in tenant_ids]
    
    def get_tenant_switches(self, limit: int = 100) -> list:
        """Get recent tenant switches."""
        return self.tenant_switches[-limit:]
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        self.query_times.clear()
        self.request_counts.clear()
        self.cross_tenant_attempts.clear()
        self.tenant_switches.clear()
        self.error_counts.clear()


# Global metrics collector instance
metrics_collector = TenantMetricsCollector()


class TenantMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect tenant metrics for monitoring and analytics.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract tenant context from request if available
        tenant_id = None
        user_id = None
        
        # Try to get tenant info from the request state (set by dependencies)
        if hasattr(request.state, 'current_tenant'):
            current_tenant = request.state.current_tenant
            tenant_id = current_tenant.tenant_id
        
        if hasattr(request.state, 'current_user'):
            user_id = request.state.current_user.id
        
        # Record the request
        metrics_collector.record_request(tenant_id)
        
        # Track tenant switches
        if request.url.path == "/api/v1/auth/switch-tenant" and request.method == "POST":
            # We'll record the switch after the response
            pass
        
        response = await call_next(request)
        
        # Record query time
        duration = time.time() - start_time
        metrics_collector.record_query_time(tenant_id, duration)
        
        # Record errors
        if response.status_code >= 400:
            metrics_collector.record_error(tenant_id, response.status_code)
        
        # Record cross-tenant access attempts (403/404 on tenant operations)
        if response.status_code in [403, 404] and "/api/v1/" in request.url.path:
            # Exclude auth endpoints from cross-tenant attempt tracking
            if "/auth/" not in request.url.path:
                metrics_collector.record_cross_tenant_attempt(tenant_id)
                logger.warning(
                    "Cross-tenant access attempt detected",
                    extra={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    }
                )
        
        # Log slow queries
        if duration > 1.0:  # Queries taking more than 1 second
            logger.warning(
                "Slow query detected",
                extra={
                    "tenant_id": tenant_id,
                    "duration": duration,
                    "path": request.url.path,
                    "method": request.method,
                }
            )
        
        return response


def get_metrics_collector() -> TenantMetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector
