"""
Tenant metrics API endpoints.
Provides access to tenant usage statistics and monitoring data.
"""
from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import admin_required, get_current_tenant, CurrentTenant
from api.middleware.tenant_metrics import get_metrics_collector

router = APIRouter()


class TenantStats(BaseModel):
    """Statistics for a single tenant."""
    tenant_id: int
    total_requests: int
    cross_tenant_attempts: int
    avg_query_time: float
    max_query_time: float
    min_query_time: float
    total_queries: int
    errors: dict


class TenantSwitchRecord(BaseModel):
    """Record of a tenant context switch."""
    timestamp: datetime
    user_id: int
    from_tenant: Optional[int]
    to_tenant: Optional[int]


class TenantMetricsResponse(BaseModel):
    """Response containing tenant metrics."""
    tenants: List[TenantStats]
    total_tenants: int


class TenantSwitchesResponse(BaseModel):
    """Response containing tenant switch history."""
    switches: List[TenantSwitchRecord]
    total: int


@router.get("/stats", response_model=TenantMetricsResponse)
async def get_tenant_metrics(
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantMetricsResponse:
    """
    Get metrics for all tenants (super-admin only).
    Returns usage statistics, performance metrics, and security events.
    """
    if not current_tenant.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can view tenant metrics"
        )
    
    collector = get_metrics_collector()
    stats = collector.get_all_tenant_stats()
    
    return TenantMetricsResponse(
        tenants=[TenantStats(**s) for s in stats],
        total_tenants=len(stats)
    )


@router.get("/stats/{tenant_id}", response_model=TenantStats)
async def get_tenant_stats(
    tenant_id: int,
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantStats:
    """
    Get metrics for a specific tenant (super-admin only).
    """
    if not current_tenant.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can view tenant metrics"
        )
    
    collector = get_metrics_collector()
    stats = collector.get_tenant_stats(tenant_id)
    
    return TenantStats(**stats)


@router.get("/switches", response_model=TenantSwitchesResponse)
async def get_tenant_switches(
    limit: int = Query(100, ge=1, le=1000),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> TenantSwitchesResponse:
    """
    Get tenant context switch history (super-admin only).
    Useful for auditing and security monitoring.
    """
    if not current_tenant.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can view tenant switches"
        )
    
    collector = get_metrics_collector()
    switches = collector.get_tenant_switches(limit=limit)
    
    return TenantSwitchesResponse(
        switches=[TenantSwitchRecord(**s) for s in switches],
        total=len(switches)
    )


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_metrics(
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
):
    """
    Reset all metrics (super-admin only).
    Useful for testing or starting fresh monitoring period.
    """
    if not current_tenant.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can reset metrics"
        )
    
    collector = get_metrics_collector()
    collector.reset()
