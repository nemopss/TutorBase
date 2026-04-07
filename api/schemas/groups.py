from __future__ import annotations

from datetime import datetime

from pydantic import Field

from api.schemas.base import BaseRequest, BaseResponse, TimestampMixin


class LearnerGroupCreateRequest(BaseRequest):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=32)
    learner_ids: list[int] = Field(default_factory=list, max_length=500)


class LearnerGroupUpdateRequest(BaseRequest):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=32)
    status: str | None = Field(None, pattern="^(active|paused|archived)$")


class LearnerGroupMembersRequest(BaseRequest):
    learner_ids: list[int] = Field(..., min_length=1, max_length=500)


class LearnerGroupMemberResponse(BaseResponse):
    learner_id: int
    display_name: str
    status: str
    joined_at: datetime | None = None
    left_at: datetime | None = None


class LearnerGroupResponse(BaseResponse, TimestampMixin):
    id: int
    name: str
    description: str | None = None
    color: str | None = None
    status: str
    member_count: int = 0
    members: list[LearnerGroupMemberResponse] = Field(default_factory=list)
