from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.schemas.registration import validate_email_format


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


class EmailPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320, description="Email address")
    password: str = Field(..., min_length=8, max_length=256, description="Password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validate_email_format(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Password cannot be empty")
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class BrowserTutorRegistrationRequest(EmailPasswordRequest):
    school_name: str = Field(..., min_length=2, max_length=100, description="Name of the school or tutoring business")
    tutor_name: Optional[str] = Field(None, max_length=100, description="Tutor's display name")
    offer_accepted: bool = Field(False, description="User accepted the public offer")
    privacy_accepted: bool = Field(False, description="User accepted personal data processing policy")

    @field_validator("school_name")
    @classmethod
    def validate_school_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("School name cannot be empty")
        return value

    @field_validator("tutor_name")
    @classmethod
    def validate_tutor_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("offer_accepted")
    @classmethod
    def validate_offer_accepted(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Public offer acceptance is required")
        return value

    @field_validator("privacy_accepted")
    @classmethod
    def validate_privacy_accepted(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Personal data processing consent is required")
        return value


class UserPayload(BaseModel):
    id: int
    role: str
    is_platform_admin: bool = False
    display_name: str
    username: Optional[str]
    telegram_id: Optional[int]
    email: Optional[str] = None
    email_verified_at: Optional[datetime] = None
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
