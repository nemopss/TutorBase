from __future__ import annotations

from pydantic import BaseModel


class LearnerResponse(BaseModel):
    id: int
    display_name: str


class LearnerListResponse(BaseModel):
    items: list[LearnerResponse]
