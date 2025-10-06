from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WebAppLoginRequest(BaseModel):
    init_data: str = Field(..., description="Raw initData string from Telegram WebApp")


class RefreshRequest(BaseModel):
    refresh_token: str


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

