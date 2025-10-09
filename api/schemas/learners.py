from __future__ import annotations

from pydantic import BaseModel, Field


class LearnerResponse(BaseModel):
    id: int
    display_name: str
    notifications_enabled: bool = True
    chat_id: int | None = None


class LearnerListResponse(BaseModel):
    items: list[LearnerResponse]


class CreateLearnerFromChatIdRequest(BaseModel):
    chat_id: int = Field(..., description="Telegram chat_id")
    display_name: str = Field(..., min_length=1, description="Display name for the learner")
    notes: str | None = Field(None, description="Optional notes")


class UpdateLearnerNotificationsRequest(BaseModel):
    notifications_enabled: bool = Field(..., description="Enable or disable notifications")
