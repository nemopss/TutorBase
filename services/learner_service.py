from __future__ import annotations

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from database.models import Learner


async def get_all_learners(session: AsyncSession, current_tenant: CurrentTenant) -> list[Learner]:
    """Fetches all learners, respecting tenant isolation."""
    return await crud.fetch_all_learners(session, current_tenant)


async def create_learner_from_chat_id(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    chat_id: int,
    display_name: str,
    notes: Optional[str] = None,
    notifications_enabled: bool = True,
    tenant_id: Optional[int] = None, # For super_admin usage
) -> Learner:
    """Creates a learner from a chat_id, handling tenant context."""
    learner = await crud.create_learner_from_chat_id(
        session,
        current_tenant,
        chat_id=chat_id,
        display_name=display_name,
        notes=notes,
        notifications_enabled=notifications_enabled,
        tenant_id=tenant_id,
    )
    await session.flush()
    await session.refresh(learner, attribute_names=["bot_user"])
    return learner


async def update_learner_notifications(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    notifications_enabled: bool,
) -> Learner | None:
    """Updates a learner's notification settings, checking for ownership."""
    # First, get the learner ensuring it belongs to the current tenant.
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        return None
    
    # Then, update it.
    return await crud.update_learner(
        session,
        current_tenant,
        learner,
        notifications_enabled=notifications_enabled,
    )