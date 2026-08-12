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
from notifications.application.settings import RebuildLearnerNotificationQueueUseCase
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork


async def refresh_learner_notification_schedules(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner: Learner,
    *,
    reason: str,
) -> None:
    """Refresh both notification systems after learner contact/preference changes."""
    tenant_id = current_tenant.tenant_id or learner.tenant_id
    if tenant_id is None:
        return

    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    await RebuildLearnerNotificationQueueUseCase(uow).execute(
        learner_id=learner.id,
        reason=reason,
        commit=False,
    )

    if not learner.notifications_enabled or learner.bot_user_id is None:
        return

    from services.package_scheduler import regenerate_package_reminders

    packages = await crud.fetch_lesson_packages_for_learner(
        session,
        current_tenant,
        learner.id,
    )
    for package in packages:
        await regenerate_package_reminders(session, current_tenant, package)


async def get_all_learners(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    archive_status: str = "active",
) -> list[Learner]:
    """Retrieve all learners for the current tenant.

    Fetches all learners belonging to the current tenant, respecting multi-tenancy
    isolation. Results include learner details and associated bot_user information.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy

    Returns:
        List of Learner models for the current tenant
    """
    return await crud.fetch_all_learners(session, current_tenant, archive_status=archive_status)


async def get_learner_by_id(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
) -> Learner | None:
    """Retrieve a learner by ID.

    Fetches a single learner by ID, respecting multi-tenancy isolation.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of the learner to retrieve

    Returns:
        Learner model if found, None otherwise
    """
    return await crud.get_learner(session, current_tenant, learner_id)


async def create_learner_from_chat_id(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    chat_id: int | None,
    display_name: str,
    notes: Optional[str] = None,
    notifications_enabled: bool = True,
    tenant_id: Optional[int] = None,  # For super_admin usage
    lesson_rate: Optional[float] = None,
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
        lesson_rate: Individual lesson rate for this learner (optional)

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
        lesson_rate=lesson_rate,
    )
    await session.flush()
    await session.refresh(learner, attribute_names=["bot_user"])
    if learner.bot_user_id is not None:
        await refresh_learner_notification_schedules(
            session,
            current_tenant,
            learner,
            reason="learner_contact_linked",
        )
    return learner


async def update_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
    display_name: Optional[str] = None,
    notes: Optional[str] = None,
    notifications_enabled: Optional[bool] = None,
    lesson_rate: Optional[float] = None,
) -> Learner | None:
    """Update learner details.

    Updates learner fields. Only provided (non-None) fields will be updated.
    First verifies that the learner belongs to the current tenant before updating.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner to update
        display_name: New display name (optional)
        notes: New notes (optional)
        notifications_enabled: New notification preference (optional)
        lesson_rate: New lesson rate (optional)

    Returns:
        Updated Learner model if found, None if learner doesn't exist or doesn't
        belong to current tenant
    """
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        return None
    if learner.archived_at is not None and notifications_enabled:
        raise ValueError("Cannot enable notifications for archived learner")

    previous_notifications_enabled = learner.notifications_enabled
    updated = await crud.update_learner(
        session,
        current_tenant,
        learner,
        display_name=display_name,
        notes=notes,
        notifications_enabled=notifications_enabled,
        lesson_rate=lesson_rate,
    )
    if (
        notifications_enabled is not None
        and notifications_enabled != previous_notifications_enabled
    ):
        await refresh_learner_notification_schedules(
            session,
            current_tenant,
            updated,
            reason="learner_notifications_changed",
        )
    return updated


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
    if learner.archived_at is not None and notifications_enabled:
        raise ValueError("Cannot enable notifications for archived learner")

    previous_notifications_enabled = learner.notifications_enabled
    # Then, update it.
    updated = await crud.update_learner(
        session,
        current_tenant,
        learner,
        notifications_enabled=notifications_enabled,
    )
    if notifications_enabled != previous_notifications_enabled:
        await refresh_learner_notification_schedules(
            session,
            current_tenant,
            updated,
            reason="learner_notifications_changed",
        )
    return updated


async def archive_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
) -> Learner | None:
    """Soft-archive learner and disable notifications."""
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        return None
    archived = await crud.archive_learner(session, current_tenant, learner)
    await refresh_learner_notification_schedules(
        session,
        current_tenant,
        archived,
        reason="learner_archived",
    )
    return archived


async def restore_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
) -> Learner | None:
    """Return learner to active lists without changing notification preference."""
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        return None
    return await crud.restore_learner(session, current_tenant, learner)


async def delete_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner_id: int,
) -> bool:
    """Archive a learner while preserving lesson and financial history.

    Archives the learner and disables notifications while preserving packages,
    lessons, payments, and audit history.

    Args:
        session: Async database session
        current_tenant: Current tenant context for multi-tenancy
        learner_id: ID of learner to delete

    Returns:
        True if learner was archived, False if learner doesn't exist or doesn't
        belong to current tenant
    """
    learner = await crud.get_learner(session, current_tenant, learner_id)
    if not learner:
        return False
    
    await archive_learner(session, current_tenant, learner_id=learner_id)
    return True
