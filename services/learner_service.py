"""Service for managing learners in the system.

This module contains business logic for working with learners (students who
receive lessons). Learners are linked to Telegram bot users and belong to
specific tenants for multi-tenancy isolation.

Key components:
    - get_all_learners: Retrieve all learners for current tenant
    - create_learner_from_chat_id: Create a new learner from Telegram chat ID
    - update_learner_notifications: Update learner notification preferences

Relationships with other services:
    - package_service: Learners own lesson packages
    - lesson_service: Learners receive lessons through packages
    - bot handlers: Learners are created/managed via Telegram bot

Business logic:
    - All operations respect tenant isolation for multi-tenancy
    - Learners are linked to BotUser via chat_id
    - Notification settings control reminder delivery
    - Super admins can specify tenant_id when creating learners
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from database.models import Learner


async def get_all_learners(session: AsyncSession, current_tenant: CurrentTenant) -> list[Learner]:
    """Retrieve all learners for the current tenant.

    Fetches all learners belonging to the current tenant, respecting multi-tenancy
    isolation. Results include learner details and associated bot_user information.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy

    Returns:
        List of Learner models for the current tenant
    """
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
    """Create a new learner linked to a Telegram chat ID.

    Creates a learner record and links it to an existing or new BotUser identified
    by chat_id. The learner is associated with the current tenant unless tenant_id
    is explicitly provided (super admin only).

    After creation, the learner is flushed to database and refreshed to load the
    bot_user relationship.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        chat_id: Telegram chat ID to link learner to
        display_name: Display name for the learner
        notes: Additional notes about the learner (optional)
        notifications_enabled: Whether to enable notifications (default True)
        tenant_id: Explicit tenant ID for super admin usage (optional)

    Returns:
        Created Learner model with bot_user relationship loaded
    """
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
    """Update learner notification preferences.

    Updates whether the learner should receive notifications (reminders for lessons).
    First verifies that the learner belongs to the current tenant before updating.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner to update
        notifications_enabled: New notification preference (True to enable, False to disable)

    Returns:
        Updated Learner model if found, None if learner doesn't exist or doesn't
        belong to current tenant
    """
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