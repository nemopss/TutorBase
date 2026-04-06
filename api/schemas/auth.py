from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WebAppLoginRequest(BaseModel):
    init_data: str = Field(..., description="Raw initData string from Telegram WebApp")


class RefreshRequest(BaseModel):
    refresh_token: str


class SwitchTenantRequest(BaseModel):
    tenant_id: Optional[int] = Field(None, description="Tenant ID to switch to, or null for global context")


class TelegramLoginWidgetRequest(BaseModel):
    id: int = Field(..., description="Telegram user ID")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int = Field(..., description="Telegram Login Widget auth timestamp")
    hash: str = Field(..., description="Telegram Login Widget verification hash")


class UserPayload(BaseModel):
    id: int
    role: str
    display_name: str
    username: Optional[str]
    telegram_id: Optional[int]
    last_login_at: Optional[datetime]


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPayload


class BrowserTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPayload
