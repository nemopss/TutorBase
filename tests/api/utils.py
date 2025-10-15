from __future__ import annotations

import random

from api.security import create_access_token
from database import crud
from sqlalchemy.ext.asyncio import AsyncSession


async def make_auth_headers(
    session: AsyncSession,
    *,
    role: str = "admin",
    telegram_id: int | None = None,
    username: str = "tester",
    display_name: str = "API Tester",
) -> tuple[dict[str, str], int]:
    """Create a user with given role and return Authorization header + user id."""
    telegram_id = telegram_id or random.randint(10_000, 1_000_000)

    user = await crud.create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
        role=role,
    )
    await session.commit()

    token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "telegram_id": user.telegram_id,
        }
    )
    return {"Authorization": f"Bearer {token}"}, user.id
