from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


UserRole = Literal["admin", "teacher", "viewer"]


class UserItem(BaseModel):
    id: int
    display_name: str
    username: Optional[str]
    telegram_id: Optional[int]
    role: UserRole
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]


class UserListResponse(BaseModel):
    users: list[UserItem]


class UpdateUserRoleRequest(BaseModel):
    role: UserRole
