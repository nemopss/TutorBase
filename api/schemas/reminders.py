from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class ReminderResponse(BaseModel):
    id: int
    package_id: int
    lesson_id: Optional[int]
    reminder_type: Optional[str]
    scheduled_for: datetime
    status: str
    active: bool
    payload: dict[str, Any]
    comment: Optional[str]
    last_notified_at: Optional[datetime]
    last_response: Optional[str]
    last_response_at: Optional[datetime]
    last_decline_reason: Optional[str]


class ReminderListResponse(BaseModel):
    total: int
    items: list[ReminderResponse]


class ReminderUpdateRequest(BaseModel):
    status: Optional[str] = None
    active: Optional[bool] = None
    comment: Optional[str] = None

