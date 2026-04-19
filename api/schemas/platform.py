from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TenantAccessResponse(BaseModel):
    tenant_id: Optional[int]
    status: str
    mode: str
    access_until: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    is_lifetime: bool
    reason: Optional[str] = None
    notes: Optional[str] = None
    bypass_access_restrictions: bool = False


class PlatformTenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    contact_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    access: TenantAccessResponse


class TenantAccessSyncResponse(BaseModel):
    grace_started: int
    expired: int
    changed: int


class TenantAccessGrantRequest(BaseModel):
    days: int = Field(30, ge=1, le=3650)
    notes: Optional[str] = Field(None, max_length=1000)


class TenantAccessActionRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000)
