from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


class BroadcastRecipientPreviewResponse(BaseModel):
    bot_user_id: int
    chat_id: int
    display_name: Optional[str] = None
    username: Optional[str] = None


class BroadcastPreviewRequest(BaseModel):
    audience: str = "platform_admins"
    bot_user_ids: list[int] = Field(default_factory=list)
    sample_limit: int = Field(20, ge=1, le=100)


class BroadcastPreviewResponse(BaseModel):
    audience: str
    total: int
    sample: list[BroadcastRecipientPreviewResponse]


class BroadcastCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message_text: str = Field(..., min_length=1, max_length=4000)
    audience: str = "platform_admins"
    bot_user_ids: list[int] = Field(default_factory=list)
    rate_limit_per_second: int = Field(10, ge=1, le=20)

    @field_validator("title", "message_text")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field must not be blank")
        return value


class BroadcastSendRequest(BaseModel):
    confirmation_text: str = Field(..., max_length=32)


class BroadcastCampaignResponse(BaseModel):
    id: int
    title: str
    message_text: str
    audience: str
    status: str
    recipient_count: int
    sent_count: int
    failed_count: int
    skipped_count: int
    rate_limit_per_second: int
    last_task_id: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BroadcastRecipientResponse(BaseModel):
    id: int
    campaign_id: int
    bot_user_id: Optional[int] = None
    chat_id: int
    display_name: Optional[str] = None
    username: Optional[str] = None
    status: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None


class BroadcastAudienceUserResponse(BaseModel):
    bot_user_id: int
    chat_id: int
    display_name: Optional[str] = None
    username: Optional[str] = None
    is_platform_admin: bool = False
