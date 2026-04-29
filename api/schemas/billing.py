from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BillingPlanResponse(BaseModel):
    code: str
    name: str
    active_learners_limit: int
    monthly_price_rub: int
    yearly_price_rub: Optional[int] = None
    is_public: bool
    display_order: int


class BillingSnapshotResponse(BaseModel):
    tenant_id: int
    plan_code: str
    plan_name: str
    subscription_plan_code: Optional[str] = None
    subscription_status: Optional[str] = None
    provider: Optional[str] = None
    active_learners_limit: int
    active_learners_count: int
    monthly_price_rub: int
    yearly_price_rub: Optional[int] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    cancel_at_period_end: bool
    is_effective_free_plan: bool
    is_over_limit: bool
    can_create_learner: bool
    can_restore_learner: bool
    notifications_allowed: bool
    billing_restriction_reason: Optional[str] = None


class TenantSubscriptionGrantRequest(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=32)
    status: str = Field("manual", min_length=1, max_length=32)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)


class TenantSubscriptionCancelRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000)
