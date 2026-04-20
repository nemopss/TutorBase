"""Schemas for user registration system."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
import re


class TutorRegistrationRequest(BaseModel):
    """Request schema for tutor registration."""
    school_name: str = Field(..., min_length=2, max_length=100, description="Name of the school or tutoring business")
    contact_email: str = Field(..., description="Contact email for the tutor/school")
    tutor_name: Optional[str] = Field(None, max_length=100, description="Tutor's display name (optional, will use Telegram name if not provided)")
    
    @validator('school_name')
    def validate_school_name(cls, v):
        if not v or not v.strip():
            raise ValueError('School name cannot be empty')
        return v.strip()
    
    @validator('contact_email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError('Email cannot be empty')
        # Simple email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.strip()):
            raise ValueError('Invalid email format')
        return v.strip()


class StudentRegistrationRequest(BaseModel):
    """Request schema for student registration via invite."""
    invite_token: str = Field(..., min_length=10, description="Invite token from tutor")
    student_name: Optional[str] = Field(None, max_length=100, description="Student's display name (optional, will use Telegram name if not provided)")
    
    @validator('invite_token')
    def validate_invite_token(cls, v):
        if not v or not v.strip():
            raise ValueError('Invite token cannot be empty')
        return v.strip()


class InviteTokenRequest(BaseModel):
    """Request schema for generating invite tokens."""
    expires_in_days: Optional[int] = Field(30, ge=1, le=365, description="Number of days until token expires (default: 30)")
    note: Optional[str] = Field(None, max_length=200, description="Optional note for the invite")
    learner_id: Optional[int] = Field(None, gt=0, description="Optional learner ID for a personal invite")


class InviteTokenResponse(BaseModel):
    """Response schema for invite token."""
    id: int
    token: str
    expires_at: datetime
    created_at: datetime
    is_used: bool
    is_expired: bool
    is_valid: bool
    note: Optional[str] = None
    learner_id: Optional[int] = None
    learner_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class InviteTokenListResponse(BaseModel):
    """Response schema for listing invite tokens."""
    tokens: list[InviteTokenResponse]
    total: int


class RegistrationResponse(BaseModel):
    """Response schema for successful registration."""
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict  # Will use existing UserPayload
    tenant: dict  # Basic tenant info
    message: str = "Registration successful"
