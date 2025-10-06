from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    lesson_count: Optional[int]
    duration_days: Optional[int]
    timezone: str
    default_config: dict


class TemplateListResponse(BaseModel):
    total: int
    items: list[TemplateResponse]


class TemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    lesson_count: Optional[int] = None
    duration_days: Optional[int] = None
    timezone: str = "Europe/Moscow"
    default_config: dict = Field(default_factory=dict)


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    lesson_count: Optional[int] = None
    duration_days: Optional[int] = None
    timezone: Optional[str] = None
    default_config: Optional[dict] = None
