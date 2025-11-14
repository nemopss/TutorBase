"""CRUD operations for all database models.

This module contains Create, Read, Update, Delete operations for all entities
in the system. All operations support multi-tenancy through CurrentTenant context.

Function groups:
    - Applications: add_application, fetch_*_applications, delete_all_applications
    - Students: add_student, get_all_students, get_student, delete_student (legacy)
    - Users: get_user, create_user, update_user_login_metadata, list_users
    - BotUsers: upsert_bot_user, get_bot_user, get_bot_user_by_chat_id
    - Learners: create_learner, get_learner, update_learner, delete_learner, fetch_*_learners
    - Templates: create_lesson_package_template, get_lesson_package_template, fetch_*
    - Packages: add_lesson_package, get_lesson_package, update_lesson_package, delete_*
    - Lessons: add_lesson, get_lesson, update_lesson, delete_lesson, fetch_*_lessons
    - Reminders: create_reminder_rule, get_reminder_*, fetch_*_reminders, update_*
    - Tenants: create_tenant, get_tenant, list_tenants
    - InviteTokens: create_invite_token, get_invite_token, validate_and_use_token
"""
from __future__ import annotations
from datetime import datetime, timezone, date
from email.mime import base
from typing import Optional, TYPE_CHECKING

from aiogram.types import User as AiogramUser
from sqlalchemy import select, func, or_, and_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

if TYPE_CHECKING:
    from api.dependencies import CurrentTenant

from utils.tenant import resolve_tenant_id
from database.models import (
    Application,
    Student,
    BotUser,
    InviteToken,
    Learner,
    LessonPackageTemplate,
    LessonPackage,
    Lesson,
    ReminderRule,
    ReminderInstance,
    User,
    Tenant,
)
from database.validators import escape_like_pattern


# ============================================================================
# Application CRUD Operations
# ============================================================================


async def add_application(session: AsyncSession, current_tenant: CurrentTenant, app_data: dict, tenant_id: Optional[int] = None):
    """Add new student application.
    
    Super admins can specify tenant_id, otherwise uses current tenant.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        app_data: Application data dictionary
        tenant_id: Optional tenant ID (super admin only)
    """
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

    new_app = Application(**app_data, tenant_id=final_tenant_id)
    session.add(new_app)


async def fetch_last_n_applications(session: AsyncSession, current_tenant: CurrentTenant, n: int = 20):
    """Fetch last N applications ordered by ID descending.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        n: Number of applications to fetch
        
    Returns:
        List of Application objects
    """
    query = select(Application).order_by(Application.id.desc())
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    query = query.limit(n)
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_all_applications(session: AsyncSession, current_tenant: CurrentTenant):
    """Fetch all applications ordered by ID ascending.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        List of all Application objects
    """
    query = select(Application).order_by(Application.id.asc())
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_applications_count(session: AsyncSession, current_tenant: CurrentTenant):
    """Get total count of applications.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        Total number of applications
    """
    query = select(func.count()).select_from(Application)
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    result = await session.execute(query)
    return result.scalar_one()


async def fetch_applications_stats(session: AsyncSession, current_tenant: CurrentTenant) -> dict:
    """Get aggregate statistics for applications.
    
    Calculates statistics by language, by month, and recent applications.
    Handles both SQLite and PostgreSQL date formatting.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        Dictionary with keys: total, by_language, by_month, recent
    """
    base_query = select(Application)
    if current_tenant.tenant_id is not None:
        base_query = base_query.where(Application.tenant_id == current_tenant.tenant_id)

    by_language_query = (
        base_query.with_only_columns(Application.language, func.count())
        .group_by(Application.language)
    )
    by_language_result = await session.execute(by_language_query)
    # Сохраняем результат, чтобы использовать его дважды
    by_language_rows = by_language_result.all()
    by_language = {lang or '—': count for lang, count in by_language_rows}
    total = sum(by_language.values())

    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else 'sqlite'
    if dialect == 'sqlite':
        month_expr = func.strftime('%Y-%m', Application.created_at)
    else:
        month_expr = func.to_char(Application.created_at, 'YYYY-MM')

    month_labeled = month_expr.label('month')
    by_month_query = base_query.with_only_columns(month_labeled, func.count()).group_by(month_labeled).order_by(month_labeled)
    by_month_result = await session.execute(by_month_query)
    by_month = {month or '—': count for month, count in by_month_result.all()}

    recent_query = (
        base_query.with_only_columns(Application)
        .order_by(Application.created_at.desc())
        .limit(5)
    )
    recent_rows = (await session.execute(recent_query)).scalars().all()

    return {
        'total': total,
        'by_language': by_language,
        'by_month': by_month,
        'recent': recent_rows,
    }


async def delete_all_applications(session: AsyncSession, current_tenant: CurrentTenant):
    """Delete all applications (DANGEROUS operation).
    
    Super-admins can delete across all tenants.
    Regular users can only delete from their own tenant.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
    """
    query = select(Application)
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    
    result = await session.execute(query)
    for app in result.scalars().all():
        await session.delete(app)


# ============================================================================
# Student CRUD Operations (Legacy)
# ============================================================================


async def add_student(session: AsyncSession, name: str, story: str, photo_file_id: str | None = None):
    """Add new student (legacy model).
    
    Args:
        session: Async database session
        name: Student name
        story: Student story/description
        photo_file_id: Telegram file ID for photo
    """
    new_student = Student(name=name, story=story, photo_file_id=photo_file_id)
    session.add(new_student)


async def get_all_students(session: AsyncSession):
    """Get all students ordered by name (legacy model).
    
    Args:
        session: Async database session
        
    Returns:
        List of Student objects
    """
    query = select(Student).order_by(Student.name)
    result = await session.execute(query)
    return result.scalars().all()


async def get_student(session: AsyncSession, student_id: int):
    """Get student by ID (legacy model).
    
    Args:
        session: Async database session
        student_id: Student ID
        
    Returns:
        Student object or None
    """
    return await session.get(Student, student_id)


async def delete_student(session: AsyncSession, student_id: int):
    """Delete student by ID (legacy model).
    
    Args:
        session: Async database session
        student_id: Student ID to delete
    """
    student = await session.get(Student, student_id)
    if student:
        await session.delete(student)


# ============================================================================
# User CRUD Operations
# ============================================================================


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    """Get user by ID.
    
    Args:
        session: Async database session
        user_id: User ID
        
    Returns:
        User object or None
    """
    return await session.get(User, user_id)


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Get user by Telegram ID.
    
    Args:
        session: Async database session
        telegram_id: Telegram user ID
        
    Returns:
        User object or None
    """
    stmt = select(User).where(User.telegram_id == telegram_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    telegram_id: int | None,
    username: str | None,
    display_name: str,
    role: str = "viewer",
    tenant_id: Optional[int] = None,
) -> User:
    """Create new system user.
    
    Validates input and assigns tenant based on permissions.
    Super-admins can create users for any tenant or global admins.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        telegram_id: Optional Telegram ID for linking
        username: Optional username
        display_name: Display name (required)
        role: User role (viewer, teacher, admin)
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created User object
        
    Raises:
        ValueError: If validation fails
    """
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    # Super-admins created without a tenant_id should be global
    elif current_tenant.is_super_admin and role == 'admin':
        final_tenant_id = None
    else:
        final_tenant_id = current_tenant.tenant_id
    
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
        role=role,
        created_at=now,
        updated_at=now,
        last_login_at=now,
        tenant_id=final_tenant_id,
    )
    session.add(user)
    return user


async def update_user_login_metadata(
    session: AsyncSession,
    user: User,
    *,
    username: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    last_login_at: datetime | None = None,
) -> User:
    """Update user login metadata and profile.
    
    Updates user information and last login timestamp.
    Invalidates user cache if role is changed (critical for permissions).
    
    Args:
        session: Async database session
        user: User object to update
        username: New username
        display_name: New display name
        role: New role (invalidates cache if changed)
        last_login_at: Last login timestamp (defaults to now)
        
    Returns:
        Updated User object
    """
    from utils.cache import invalidate_cache
    
    now = datetime.now(timezone.utc)
    role_changed = False
    
    if username is not None:
        user.username = username
    if display_name is not None:
        user.display_name = display_name
    if role is not None and user.role != role:
        user.role = role
        role_changed = True
    if last_login_at is not None:
        user.last_login_at = last_login_at
    else:
        user.last_login_at = now
    user.updated_at = now
    session.add(user)
    
    # Invalidate cache if role changed (critical for permission checks)
    if role_changed:
        await invalidate_cache("users:_get_user_cached:*")
    
    return user


async def list_users(session: AsyncSession, current_tenant: CurrentTenant) -> list[User]:
    """List all users for current tenant.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        List of User objects ordered by creation date
    """
    stmt = select(User).order_by(User.created_at.asc())
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(User.tenant_id == current_tenant.tenant_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_users_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    """List users for current tenant with pagination.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        limit: Maximum number of records to return
        offset: Number of records to skip
        
    Returns:
        Tuple of (list of User objects, total count)
    """
    # Base query for filtering
    base_stmt = select(User)
    if current_tenant.tenant_id is not None:
        base_stmt = base_stmt.where(User.tenant_id == current_tenant.tenant_id)
    
    # Count query
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0
    
    # Data query with pagination
    stmt = base_stmt.order_by(User.created_at.asc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    return users, total


# ============================================================================
# BotUser CRUD Operations
# ============================================================================


async def upsert_bot_user(session: AsyncSession, user: AiogramUser) -> BotUser:
    """Create or update bot user from Telegram user.
    
    Updates existing user or creates new one based on chat_id.
    Updates last_seen_at timestamp on every call.
    
    Args:
        session: Async database session
        user: Aiogram User object from Telegram
        
    Returns:
        BotUser object (created or updated)
    """
    now_utc = datetime.now(timezone.utc)
    stmt = select(BotUser).where(BotUser.chat_id == user.id)
    existing = (await session.execute(stmt)).scalar_one_or_none()

    username = user.username
    first_name = getattr(user, 'first_name', None)
    last_name = getattr(user, 'last_name', None)
    language_code = getattr(user, 'language_code', None)
    is_bot = bool(getattr(user, 'is_bot', False))

    if existing:
        existing.username = username
        existing.first_name = first_name
        existing.last_name = last_name
        existing.language_code = language_code
        existing.is_bot = is_bot
        existing.updated_at = now_utc
        existing.last_seen_at = now_utc
        session.add(existing)
        return existing

    new_bot_user = BotUser(
        chat_id=user.id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        is_bot=is_bot,
        created_at=now_utc,
        updated_at=now_utc,
        last_seen_at=now_utc,
    )
    session.add(new_bot_user)
    return new_bot_user


async def fetch_available_bot_users(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: Optional[str] = None,
) -> tuple[list[BotUser], int]:
    """Fetch bot users not yet linked to learners with pagination.
    
    Searches across username, first_name, last_name, and chat_id.
    
    Args:
        session: Async database session
        limit: Maximum number of results
        offset: Number of results to skip
        search: Optional search string
        
    Returns:
        Tuple of (list of BotUser objects, total count)
    """
    base_query = select(BotUser).outerjoin(Learner).where(Learner.id.is_(None))

    if search:
        from database.validators import escape_like_pattern
        escaped_search = escape_like_pattern(search.lower())
        pattern = f"%{escaped_search}%"
        chat_id_expr = cast(BotUser.chat_id, String)
        base_query = base_query.where(
            or_(
                func.lower(func.coalesce(BotUser.username, '')).like(pattern),
                func.lower(func.coalesce(BotUser.first_name, '')).like(pattern),
                func.lower(func.coalesce(BotUser.last_name, '')).like(pattern),
                chat_id_expr.like(pattern),
            )
        )

    count_stmt = base_query.with_only_columns(func.count()).order_by(None)
    total = (await session.execute(count_stmt)).scalar_one()

    rows_stmt = base_query.order_by(BotUser.first_name.asc(), BotUser.chat_id.asc()).offset(offset).limit(limit)
    rows = (await session.execute(rows_stmt)).scalars().all()

    return rows, total


# ============================================================================
# Learner CRUD Operations
# ============================================================================


async def fetch_learners_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Learner], int]:
    """Fetch learners with pagination and tenant filtering.
    
    Super-admins in global context see all learners.
    Regular users and switched super-admins see only their tenant's learners.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        Tuple of (list of Learner objects with bot_user loaded, total count)
    """
    base_query = select(Learner)

    # Apply tenant filter:
    # - Regular users: always filter by their tenant
    # - Super-admins in global context (tenant_id=None): no filter, see all data
    # - Super-admins in switched context (tenant_id=X): filter by that tenant
    if current_tenant.tenant_id is not None:
        base_query = base_query.where(Learner.tenant_id == current_tenant.tenant_id)

    # Count query - use select(func.count()) for correct counting
    count_query = select(func.count()).select_from(Learner)
    if current_tenant.tenant_id is not None:
        count_query = count_query.where(Learner.tenant_id == current_tenant.tenant_id)
    
    total = (await session.execute(count_query)).scalar_one()

    if total == 0:
        return [], 0

    rows_stmt = (
        base_query
        .options(selectinload(Learner.bot_user))
        .order_by(Learner.display_name.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()
    return rows, total


async def create_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    bot_user_id: int,
    display_name: str,
    notes: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Learner:
    """Create new learner linked to bot user.
    
    Super-admins can specify tenant_id, otherwise uses current tenant.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        bot_user_id: ID of bot user to link
        display_name: Display name for learner
        notes: Optional notes about learner
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created Learner object
    """
    now_utc = datetime.now(timezone.utc)
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)

    learner = Learner(
        bot_user_id=bot_user_id,
        display_name=display_name,
        notes=notes,
        created_at=now_utc,
        tenant_id=final_tenant_id,
    )
    session.add(learner)
    return learner


async def get_bot_user(session: AsyncSession, bot_user_id: int) -> BotUser | None:
    """Get bot user by ID.
    
    Args:
        session: Async database session
        bot_user_id: Bot user ID
        
    Returns:
        BotUser object or None
    """
    return await session.get(BotUser, bot_user_id)


async def get_bot_user_by_chat_id(session: AsyncSession, chat_id: int) -> BotUser | None:
    """Get bot user by Telegram chat ID.
    
    Args:
        session: Async database session
        chat_id: Telegram chat ID
        
    Returns:
        BotUser object or None
    """
    stmt = select(BotUser).where(BotUser.chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner(session: AsyncSession, current_tenant: CurrentTenant, learner_id: int) -> Learner | None:
    """Get learner by ID with tenant filtering.
    
    Eager loads bot_user relationship.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        learner_id: Learner ID
        
    Returns:
        Learner object with bot_user loaded or None
    """
    stmt = select(Learner).options(selectinload(Learner.bot_user)).where(Learner.id == learner_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Learner.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner_by_bot_user(session: AsyncSession, current_tenant: CurrentTenant, bot_user_id: int) -> Learner | None:
    """Get learner by bot user ID with tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        bot_user_id: Bot user ID
        
    Returns:
        Learner object or None
    """
    stmt = select(Learner).where(Learner.bot_user_id == bot_user_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Learner.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner: Learner,
    *,
    display_name: Optional[str] = None,
    notes: Optional[str] = None,
    notifications_enabled: Optional[bool] = None,
) -> Learner:
    """Update learner with tenant validation.
    
    Validates that learner belongs to current tenant before updating.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner: Learner object to update
        display_name: New display name
        notes: New notes
        notifications_enabled: Enable/disable notifications
        
    Returns:
        Updated Learner object
        
    Raises:
        ValueError: If learner doesn't belong to current tenant
    """
    # Security check: Ensure learner belongs to current tenant
    if not current_tenant.is_super_admin and learner.tenant_id != current_tenant.tenant_id:
        raise ValueError(f"Learner {learner.id} does not belong to tenant {current_tenant.tenant_id}")
    
    if display_name is not None:
        learner.display_name = display_name
    if notes is not None:
        learner.notes = notes
    if notifications_enabled is not None:
        learner.notifications_enabled = notifications_enabled
    session.add(learner)
    return learner


async def delete_learner(session: AsyncSession, current_tenant: CurrentTenant, learner: Learner) -> None:
    """Delete learner with tenant validation.
    
    Validates that learner belongs to current tenant before deletion.
    Cascades to delete related packages, lessons, and reminders.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner: Learner object to delete
        
    Raises:
        ValueError: If learner doesn't belong to current tenant
    """
    # Security check: Ensure learner belongs to current tenant
    if not current_tenant.is_super_admin and learner.tenant_id != current_tenant.tenant_id:
        raise ValueError(f"Cannot delete learner {learner.id} - does not belong to tenant {current_tenant.tenant_id}")
    
    await session.delete(learner)


async def fetch_all_learners(session: AsyncSession, current_tenant: CurrentTenant) -> list[Learner]:
    """Fetch all learners with tenant filtering.
    
    Eager loads bot_user relationship and orders by display name.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        List of Learner objects with bot_user loaded
    """
    stmt = (
        select(Learner)
        .options(selectinload(Learner.bot_user))
        .order_by(Learner.display_name.asc())
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Learner.tenant_id == current_tenant.tenant_id)

    result = await session.execute(stmt)
    return result.scalars().all()


async def create_learner_from_chat_id(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    chat_id: int,
    display_name: str,
    notes: Optional[str] = None,
    notifications_enabled: bool = True,
    tenant_id: Optional[int] = None,
) -> Learner:
    """Create learner from Telegram chat ID.
    
    Creates or finds BotUser by chat_id, then creates Learner linked to it.
    Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        chat_id: Telegram chat ID
        display_name: Display name for learner
        notes: Optional notes
        notifications_enabled: Enable notifications (default True)
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created Learner object
    """
    now_utc = datetime.now(timezone.utc)
    
    # Try to get existing BotUser
    bot_user = await get_bot_user_by_chat_id(session, chat_id)
    
    if not bot_user:
        # Create new BotUser if it doesn't exist
        bot_user = BotUser(
            chat_id=chat_id,
            username=None,
            first_name=display_name,
            last_name=None,
            language_code=None,
            is_bot=False,
            created_at=now_utc,
            updated_at=now_utc,
            last_seen_at=now_utc,
        )
        session.add(bot_user)
    
    # Check if learner already exists for this bot_user
    existing_learner = await get_learner_by_bot_user(session, current_tenant, bot_user.id)
    if existing_learner:
        if existing_learner.notifications_enabled != notifications_enabled:
            existing_learner.notifications_enabled = notifications_enabled
            session.add(existing_learner)
        return existing_learner
    
    # Create new learner
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)

    learner = Learner(
        bot_user_id=bot_user.id,
        display_name=display_name,
        notes=notes,
        notifications_enabled=notifications_enabled,
        created_at=now_utc,
        tenant_id=final_tenant_id,
    )
    learner.bot_user = bot_user
    session.add(learner)
    return learner


# ============================================================================
# LessonPackageTemplate CRUD Operations
# ============================================================================


async def create_lesson_package_template(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    name: str,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_timezone: str = "Europe/Moscow",
    default_config: Optional[dict] = None,
    tenant_id: Optional[int] = None,
) -> LessonPackageTemplate:
    """Create new lesson package template.
    
    Validates input and assigns tenant. Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        name: Template name (required, unique)
        description: Template description
        lesson_count: Default number of lessons
        duration_days: Default duration in days
        default_timezone: Default timezone for lessons
        default_config: JSON configuration
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created LessonPackageTemplate object
        
    Raises:
        ValueError: If validation fails
    """
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id
    
    template = LessonPackageTemplate(
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone=default_timezone,
        default_config=default_config or {},
        tenant_id=final_tenant_id,
    )
    session.add(template)
    return template


async def get_lesson_package_template(session: AsyncSession, current_tenant: CurrentTenant, template_id: int) -> LessonPackageTemplate | None:
    """Get lesson package template by ID with tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        template_id: Template ID
        
    Returns:
        LessonPackageTemplate object or None
    """
    stmt = select(LessonPackageTemplate).where(LessonPackageTemplate.id == template_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackageTemplate.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_lesson_package_templates(session: AsyncSession, current_tenant: CurrentTenant) -> list[LessonPackageTemplate]:
    """Fetch all lesson package templates with tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        List of LessonPackageTemplate objects ordered by name
    """
    stmt = select(LessonPackageTemplate).order_by(LessonPackageTemplate.name.asc())
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackageTemplate.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalars().all()


async def update_lesson_package_template(
    session: AsyncSession,
    template: LessonPackageTemplate,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_timezone: Optional[str] = None,
    default_config: Optional[dict] = None,
) -> LessonPackageTemplate:
    """Update lesson package template.
    
    Args:
        session: Async database session
        template: Template object to update
        name: New name
        description: New description
        lesson_count: New lesson count
        duration_days: New duration
        default_timezone: New timezone
        default_config: New configuration
        
    Returns:
        Updated LessonPackageTemplate object
    """
    if name is not None:
        template.name = name
    if description is not None:
        template.description = description
    if lesson_count is not None:
        template.lesson_count = lesson_count
    if duration_days is not None:
        template.duration_days = duration_days
    if default_timezone is not None:
        template.default_timezone = default_timezone
    if default_config is not None:
        template.default_config = default_config
    session.add(template)
    return template


async def delete_lesson_package_template(session: AsyncSession, template: LessonPackageTemplate) -> None:
    """Delete lesson package template.
    
    Args:
        session: Async database session
        template: Template object to delete
    """
    await session.delete(template)


# ============================================================================
# LessonPackage CRUD Operations
# ============================================================================


async def create_lesson_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    learner: Learner,
    title: str,
    template: LessonPackageTemplate | None = None,
    status: str = "draft",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    timezone_name: str | None = None,
    total_lessons: Optional[int] = None,
    notes: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> LessonPackage:
    """Create new lesson package for learner.
    
    Validates input and assigns tenant. Can be created from template.
    Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        learner: Learner object for this package
        title: Package title
        template: Optional template to use
        status: Package status (draft, active, completed, cancelled)
        start_date: Package start date
        end_date: Package end date
        timezone_name: Timezone for lessons
        total_lessons: Total number of lessons
        notes: Package notes
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created LessonPackage object
        
    Raises:
        ValueError: If validation fails
    """
    final_tz = timezone_name or (template.default_timezone if template else "Europe/Moscow")
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)
    
    package = LessonPackage(
        learner=learner,
        template=template,
        title=title,
        status=status,
        start_date=start_date,
        end_date=end_date,
        timezone=final_tz,
        total_lessons=total_lessons,
        notes=notes,
        tenant_id=final_tenant_id,
    )
    session.add(package)
    return package


async def delete_lesson_package(session: AsyncSession, package: LessonPackage) -> None:
    """Delete lesson package.
    
    Cascades to delete all lessons and reminders in package.
    
    Args:
        session: Async database session
        package: Package object to delete
    """
    await session.delete(package)


async def update_lesson_package(
    session: AsyncSession,
    package: LessonPackage,
    **fields,
) -> LessonPackage:
    """Update lesson package fields.
    
    Dynamically updates any provided fields. Handles timezone_name -> timezone mapping.
    
    Args:
        session: Async database session
        package: Package object to update
        **fields: Fields to update
        
    Returns:
        Updated LessonPackage object
    """
    rename_mapping = {
        'timezone_name': 'timezone',
    }
    for key, value in fields.items():
        attr = rename_mapping.get(key, key)
        if hasattr(package, attr):
            setattr(package, attr, value)
    session.add(package)
    return package


async def get_lesson_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> LessonPackage | None:
    """Get lesson package by ID with all relationships loaded.
    
    Eager loads learner (with bot_user), template, lessons, reminder rules and instances.
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        package_id: Package ID
        
    Returns:
        LessonPackage object with all relationships loaded or None
    """
    stmt = (
        select(LessonPackage)
        .options(
            joinedload(LessonPackage.learner).joinedload(Learner.bot_user),
            joinedload(LessonPackage.template),
            selectinload(LessonPackage.lessons),
            selectinload(LessonPackage.reminder_rules).selectinload(ReminderRule.instances),
            selectinload(LessonPackage.reminder_instances),
        )
        .where(LessonPackage.id == package_id)
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackage.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_lesson_packages_for_learner(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    learner_id: int,
) -> list[LessonPackage]:
    """Fetch all lesson packages for specific learner.
    
    Eager loads learner (with bot_user) and template.
    Orders by creation date descending. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        learner_id: Learner ID
        
    Returns:
        List of LessonPackage objects for the learner
    """
    stmt = (
        select(LessonPackage)
        .options(
            joinedload(LessonPackage.learner).joinedload(Learner.bot_user),
            joinedload(LessonPackage.template),
        )
        .where(LessonPackage.learner_id == learner_id)
        .order_by(LessonPackage.created_at.desc())
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackage.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalars().all()


# ============================================================================
# Lesson CRUD Operations
# ============================================================================


async def create_lesson(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package: LessonPackage,
    *,
    scheduled_at: datetime,
    duration_minutes: Optional[int] = None,
    status: str = "scheduled",
    sequence_index: Optional[int] = None,
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
    tenant_id: Optional[int] = None,
) -> Lesson:
    """Create new lesson in package.
    
    Validates input and assigns tenant. Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Parent lesson package
        scheduled_at: Scheduled datetime for lesson
        duration_minutes: Lesson duration in minutes
        status: Lesson status (scheduled, completed, cancelled, rescheduled)
        sequence_index: Order in package
        teacher_notes: Notes from teacher
        homework_due_at: Homework deadline
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created Lesson object
        
    Raises:
        ValueError: If validation fails
    """
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)
    
    lesson = Lesson(
        package=package,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        status=status,
        sequence_index=sequence_index,
        teacher_notes=teacher_notes,
        homework_due_at=homework_due_at,
        tenant_id=final_tenant_id,
    )
    session.add(lesson)
    return lesson


async def get_lesson(session: AsyncSession, current_tenant: CurrentTenant, lesson_id: int) -> Lesson | None:
    """Get lesson by ID with relationships loaded.
    
    Eager loads package (with learner) and reminder rules.
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        lesson_id: Lesson ID
        
    Returns:
        Lesson object with relationships loaded or None
    """
    stmt = (
        select(Lesson)
        .options(
            joinedload(Lesson.package).joinedload(LessonPackage.learner),
            selectinload(Lesson.reminder_rules),
        )
        .where(Lesson.id == lesson_id)
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_lesson(session: AsyncSession, lesson: Lesson) -> None:
    """Delete lesson.
    
    Cascades to delete related reminder rules and instances.
    
    Args:
        session: Async database session
        lesson: Lesson object to delete
    """
    await session.delete(lesson)


async def fetch_lesson_packages_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
    learner_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[LessonPackage], int]:
    """Fetch lesson packages with pagination and filtering.
    
    Supports filtering by learner, status, and search (title or learner name).
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        limit: Maximum number of results
        offset: Number of results to skip
        learner_id: Optional learner ID filter
        status: Optional status filter
        search: Optional search string for title or learner name
        
    Returns:
        Tuple of (list of LessonPackage objects, total count)
    """
    base_query = select(LessonPackage)
    if current_tenant.tenant_id is not None:
        base_query = base_query.where(LessonPackage.tenant_id == current_tenant.tenant_id)

    if learner_id is not None:
        base_query = base_query.where(LessonPackage.learner_id == learner_id)
    if status is not None:
        base_query = base_query.where(LessonPackage.status == status)
    if search:
        from database.validators import escape_like_pattern
        escaped_search = escape_like_pattern(search)
        pattern = f"%{escaped_search}%"
        base_query = base_query.join(LessonPackage.learner).where(
            or_(
                LessonPackage.title.ilike(pattern),
                Learner.display_name.ilike(pattern),
            )
        )

    count_stmt = base_query.with_only_columns(func.count()).order_by(None)
    total = (await session.execute(count_stmt)).scalar_one()
    if total == 0:
        return [], 0

    rows_stmt = (
        base_query.options(
            joinedload(LessonPackage.learner).joinedload(Learner.bot_user),
            joinedload(LessonPackage.template),
            selectinload(LessonPackage.lessons),
        )
        .order_by(LessonPackage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()
    return rows, total


async def fetch_lessons_for_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> list[Lesson]:
    """Fetch all lessons for specific package.
    
    Eager loads package relationship. Orders by scheduled time ascending.
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        package_id: Package ID
        
    Returns:
        List of Lesson objects for the package
    """
    stmt = (
        select(Lesson)
        .options(selectinload(Lesson.package))
        .where(Lesson.package_id == package_id)
        .order_by(Lesson.scheduled_at.asc())
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalars().all()


async def list_all_lessons(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *, 
    status: Optional[str] = None, 
    search: Optional[str] = None,
    limit: int = 100, 
    offset: int = 0,
    sort_by: str = 'scheduled_at',
    sort_order: str = 'asc',
) -> tuple[list[Lesson], int]:
    """List all lessons with filtering, search, and sorting.
    
    Supports filtering by status, searching by date/package/learner,
    and sorting by any lesson field. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        status: Optional status filter
        search: Optional search string (date, package title, or learner name)
        limit: Maximum number of results
        offset: Number of results to skip
        sort_by: Field to sort by (default: scheduled_at)
        sort_order: Sort order (asc or desc)
        
    Returns:
        Tuple of (list of Lesson objects with package and learner loaded, total count)
    """
    stmt = (
        select(Lesson)
        .options(
            joinedload(Lesson.package).joinedload(LessonPackage.learner),
        )
    )
    count_stmt = select(func.count()).select_from(Lesson)

    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)
        count_stmt = count_stmt.where(Lesson.tenant_id == current_tenant.tenant_id)

    conditions: list = []
    needs_package_join = False
    needs_learner_join = False

    if status:
        conditions.append(Lesson.status == status)

    search_term = (search or "").strip()
    if search_term:
        parsed_date: Optional[date] = None
        try:
            parsed_date = date.fromisoformat(search_term)
        except ValueError:
            try:
                parsed_date = datetime.strptime(search_term, "%d.%m.%Y").date()
            except ValueError:
                parsed_date = None

        if parsed_date is not None:
            conditions.append(func.date(Lesson.scheduled_at) == parsed_date.isoformat())
        else:
            from database.validators import escape_like_pattern
            escaped_search = escape_like_pattern(search_term.lower())
            pattern = f"%{escaped_search}%"
            needs_package_join = True
            needs_learner_join = True
            conditions.append(
                or_(
                    func.lower(func.coalesce(LessonPackage.title, "")).like(pattern),
                    func.lower(func.coalesce(Learner.display_name, "")).like(pattern),
                )
            )

    if needs_package_join:
        stmt = stmt.join(LessonPackage, Lesson.package_id == LessonPackage.id)
        count_stmt = count_stmt.join(LessonPackage, Lesson.package_id == LessonPackage.id)
    if needs_learner_join:
        stmt = stmt.join(Learner, LessonPackage.learner_id == Learner.id)
        count_stmt = count_stmt.join(Learner, LessonPackage.learner_id == Learner.id)

    if conditions:
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))

    order_column = getattr(Lesson, sort_by, Lesson.scheduled_at)
    if sort_order == 'desc':
        stmt = stmt.order_by(order_column.desc())
    else:
        stmt = stmt.order_by(order_column.asc())

    total = (await session.execute(count_stmt)).scalar_one()
    if total == 0:
        return [], 0

    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all(), total


# ============================================================================
# Reminder CRUD Operations
# ============================================================================


async def create_reminder_rule(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    package: LessonPackage,
    lesson: Lesson | None,
    reminder_type: str,
    config: Optional[dict] = None,
    channel: str = "telegram",
    active: bool = True,
    tenant_id: Optional[int] = None,
) -> ReminderRule:
    """Create new reminder rule.
    
    Rules can be package-level or lesson-specific.
    Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        package: Parent lesson package
        lesson: Optional specific lesson
        reminder_type: Type of reminder
        config: JSON configuration for reminder
        channel: Notification channel (default: telegram)
        active: Whether rule is active
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created ReminderRule object
    """
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)

    rule = ReminderRule(
        package=package,
        lesson=lesson,
        reminder_type=reminder_type,
        config=config or {},
        channel=channel,
        active=active,
        tenant_id=final_tenant_id,
    )
    session.add(rule)
    return rule


async def get_reminder_rule(session: AsyncSession, current_tenant: CurrentTenant, rule_id: int) -> ReminderRule | None:
    """Get reminder rule by ID with tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        rule_id: Rule ID
        
    Returns:
        ReminderRule object or None
    """
    stmt = select(ReminderRule).where(ReminderRule.id == rule_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderRule.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_reminder_instance(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    rule: ReminderRule,
    package: LessonPackage,
    learner: Learner,
    scheduled_for: datetime,
    lesson: Lesson | None = None,
    status: str = "scheduled",
    payload: Optional[dict] = None,
    chat_identifier: Optional[str] = None,
    comment: Optional[str] = None,
    active: bool = True,
    tenant_id: Optional[int] = None,
) -> ReminderInstance:
    """Create new reminder instance.
    
    Instances are scheduled reminders to be sent to learners.
    Super-admins can specify tenant_id.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        rule: Parent reminder rule
        package: Related lesson package
        learner: Learner to receive reminder
        scheduled_for: When to send reminder
        lesson: Optional specific lesson
        status: Instance status (default: scheduled)
        payload: JSON data for reminder content
        chat_identifier: Telegram chat ID
        comment: Additional comment
        active: Whether instance is active
        tenant_id: Optional tenant ID (super admin only)
        
    Returns:
        Created ReminderInstance object
    """
    final_tenant_id = resolve_tenant_id(current_tenant, tenant_id)

    instance = ReminderInstance(
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson,
        scheduled_for=scheduled_for,
        status=status,
        payload=payload or {},
        chat_identifier=chat_identifier,
        comment=comment,
        active=active,
        tenant_id=final_tenant_id,
    )
    session.add(instance)
    return instance


async def fetch_reminder_instances_due(
    session: AsyncSession,
    now_utc: datetime,
    *,
    statuses: Optional[list[str]] = None,
) -> list[ReminderInstance]:
    """Fetch reminder instances that are due for sending.
    
    Finds active instances scheduled before now_utc with specified statuses.
    Eager loads all relationships. No tenant filtering (global query).
    
    Args:
        session: Async database session
        now_utc: Current UTC datetime
        statuses: List of statuses to include (default: scheduled, pending)
        
    Returns:
        List of ReminderInstance objects due for sending
    """
    if statuses is None:
        statuses = ["scheduled", "pending"]
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.lesson),
            selectinload(ReminderInstance.learner),
        )
        .where(
            ReminderInstance.status.in_(statuses),
            ReminderInstance.scheduled_for <= now_utc,
            ReminderInstance.active.is_(True),
        )
        .order_by(ReminderInstance.scheduled_for.asc())
    )
    return (await session.execute(stmt)).scalars().all()


async def set_reminder_instance_status(
    session: AsyncSession,
    instance: ReminderInstance,
    *,
    status: str,
    active: Optional[bool] = None,
    last_notified_at: Optional[datetime] = None,
    last_response: Optional[str] = None,
    last_response_at: Optional[datetime] = None,
    last_decline_reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> ReminderInstance:
    """Update reminder instance status and metadata.
    
    Updates status and optionally other fields like response data.
    
    Args:
        session: Async database session
        instance: ReminderInstance object to update
        status: New status
        active: New active state
        last_notified_at: Last notification timestamp
        last_response: Last response from learner
        last_response_at: Last response timestamp
        last_decline_reason: Reason if declined
        comment: Additional comment
        
    Returns:
        Updated ReminderInstance object
    """
    instance.status = status
    if active is not None:
        instance.active = active
    if last_notified_at is not None:
        instance.last_notified_at = last_notified_at
    if last_response is not None:
        instance.last_response = last_response
    if last_response_at is not None:
        instance.last_response_at = last_response_at
    if last_decline_reason is not None:
        instance.last_decline_reason = last_decline_reason
    if comment is not None:
        instance.comment = comment
    session.add(instance)
    return instance


async def deactivate_reminder_instances_for_lesson(
    session: AsyncSession,
    lesson_id: int,
) -> int:
    """Deactivate all active reminder instances for a lesson.
    
    Used when a lesson is cancelled to prevent sending reminders.
    Sets status='cancelled' and active=False for all active instances.
    
    Args:
        session: Async database session
        lesson_id: Lesson ID to deactivate reminders for
        
    Returns:
        Count of deactivated instances
    """
    stmt = (
        select(ReminderInstance)
        .where(
            ReminderInstance.lesson_id == lesson_id,
            ReminderInstance.active == True,
            ReminderInstance.status.in_(['scheduled', 'pending'])
        )
    )
    instances = (await session.execute(stmt)).scalars().all()
    
    count = 0
    for instance in instances:
        instance.status = 'cancelled'
        instance.active = False
        instance.comment = 'Lesson cancelled'
        session.add(instance)
        count += 1
    
    return count


async def get_reminder_instance(session: AsyncSession, current_tenant: CurrentTenant, instance_id: int) -> ReminderInstance | None:
    """Get reminder instance by ID with relationships loaded.
    
    Eager loads rule, package, learner, and lesson.
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        instance_id: Instance ID
        
    Returns:
        ReminderInstance object with relationships loaded or None
    """
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner),
            selectinload(ReminderInstance.lesson),
        )
        .where(ReminderInstance.id == instance_id)
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def get_reminder_instance_global(session: AsyncSession, instance_id: int) -> ReminderInstance | None:
    """Get reminder instance by ID without tenant filtering.
    
    Used by bot handlers where tenant context is not available.
    Tenant isolation is maintained by checking instance.tenant_id after retrieval.
    
    Eager loads rule, package, learner (with bot_user), and lesson.
    
    Args:
        session: Async database session
        instance_id: Instance ID
        
    Returns:
        ReminderInstance object with relationships loaded or None
    """
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner).selectinload(Learner.bot_user),
            selectinload(ReminderInstance.lesson),
        )
        .where(ReminderInstance.id == instance_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_reminder_instances_for_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
) -> list[ReminderInstance]:
    """Fetch all reminder instances for specific package.
    
    Eager loads rule, package, learner, and lesson.
    Orders by scheduled time. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        package_id: Package ID
        
    Returns:
        List of ReminderInstance objects for the package
    """
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner),
            selectinload(ReminderInstance.lesson),
        )
        .where(ReminderInstance.package_id == package_id)
        .order_by(ReminderInstance.scheduled_for.asc())
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalars().all()


async def fetch_reminder_instances_for_package_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReminderInstance], int]:
    """Fetch paginated reminder instances for specific package.
    
    Eager loads rule, package, learner, and lesson.
    Orders by scheduled time. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        package_id: Package ID
        limit: Maximum number of records to return
        offset: Number of records to skip
        
    Returns:
        Tuple of (list of ReminderInstance objects, total count)
    """
    # Base query for filtering
    base_stmt = (
        select(ReminderInstance)
        .where(ReminderInstance.package_id == package_id)
    )
    if current_tenant.tenant_id is not None:
        base_stmt = base_stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)
    
    # Count query
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0
    
    # Data query with pagination
    stmt = (
        base_stmt
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner),
            selectinload(ReminderInstance.lesson),
        )
        .order_by(ReminderInstance.scheduled_for.asc())
        .limit(limit)
        .offset(offset)
    )
    
    instances = (await session.execute(stmt)).scalars().all()
    return instances, total


async def fetch_reminder_instances_count(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    status: Optional[str] = None,
) -> int:
    """Get count of reminder instances with optional status filter.
    
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        status: Optional status filter
        
    Returns:
        Count of reminder instances
    """
    stmt = select(func.count()).select_from(ReminderInstance)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)

    if status is not None:
        stmt = stmt.where(ReminderInstance.status == status)
    result = await session.execute(stmt)
    return result.scalar_one()


async def fetch_reminder_instances_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
    status: Optional[str] = None,
    reminder_type: Optional[str] = None,
    package_id: Optional[int] = None,
    search: Optional[str] = None,
) -> tuple[list[ReminderInstance], int]:
    """Fetch reminder instances with pagination and filtering.
    
    Supports filtering by status, reminder_type, package_id, and search.
    Search looks in comment, package title, and learner name.
    Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        limit: Maximum number of results
        offset: Number of results to skip
        status: Optional status filter
        reminder_type: Optional reminder type filter
        package_id: Optional package ID filter
        search: Optional search string
        
    Returns:
        Tuple of (list of ReminderInstance objects, total count)
    """
    # Build base query with eager loading
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner),
            selectinload(ReminderInstance.lesson),
        )
    )
    
    # Build count query base
    count_stmt = select(func.count()).select_from(ReminderInstance)

    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)
        count_stmt = count_stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)
    
    # Track if we need joins for filtering
    needs_rule_join = False
    needs_package_join = False
    needs_learner_join = False
    
    # Apply filters
    conditions = []
    
    if status is not None:
        conditions.append(ReminderInstance.status == status)
    
    if reminder_type is not None:
        needs_rule_join = True
        conditions.append(ReminderRule.reminder_type == reminder_type)
    
    if package_id is not None:
        conditions.append(ReminderInstance.package_id == package_id)
    
    if search is not None:
        from database.validators import escape_like_pattern
        needs_package_join = True
        needs_learner_join = True
        # Search in comment, package title, and learner name
        escaped_search = escape_like_pattern(search)
        search_pattern = f"%{escaped_search}%"
        search_condition = or_(
            ReminderInstance.comment.ilike(search_pattern),
            LessonPackage.title.ilike(search_pattern),
            Learner.display_name.ilike(search_pattern),
        )
        conditions.append(search_condition)
    
    # Apply joins to main query if needed
    if needs_rule_join:
        stmt = stmt.join(ReminderRule, ReminderInstance.rule_id == ReminderRule.id)
        count_stmt = count_stmt.join(ReminderRule, ReminderInstance.rule_id == ReminderRule.id)
    
    if needs_package_join:
        stmt = stmt.join(LessonPackage, ReminderInstance.package_id == LessonPackage.id)
        count_stmt = count_stmt.join(LessonPackage, ReminderInstance.package_id == LessonPackage.id)
    
    if needs_learner_join:
        stmt = stmt.join(Learner, ReminderInstance.learner_id == Learner.id)
        count_stmt = count_stmt.join(Learner, ReminderInstance.learner_id == Learner.id)
    
    # Apply conditions to both queries
    if conditions:
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))
    
    # Get total count
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Apply pagination and ordering
    stmt = stmt.order_by(ReminderInstance.scheduled_for.desc()).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    instances = result.scalars().all()
    
    return instances, total


# ============================================================================
# Statistics Functions
# ============================================================================


async def count_lessons_by_status(session: AsyncSession, current_tenant: CurrentTenant) -> dict[str, int]:
    """Get count of lessons grouped by status.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        Dictionary mapping status to count
    """
    stmt = select(Lesson.status, func.count()).group_by(Lesson.status)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)
    result = await session.execute(stmt)
    return {status or 'unknown': count for status, count in result.all()}


async def count_reminders_by_status(session: AsyncSession, current_tenant: CurrentTenant) -> dict[str, int]:
    """Get count of reminder instances grouped by status.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        
    Returns:
        Dictionary mapping status to count
    """
    stmt = select(ReminderInstance.status, func.count()).group_by(ReminderInstance.status)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)
    result = await session.execute(stmt)
    return {status or 'unknown': count for status, count in result.all()}


async def lessons_daily_stats(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> list[tuple[str, int]]:
    """Get daily lesson counts with optional date range.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        from_date: Optional start date filter
        to_date: Optional end date filter
        
    Returns:
        List of tuples (date_string, count) ordered by date
    """
    stmt = select(func.date(Lesson.scheduled_at), func.count()).group_by(func.date(Lesson.scheduled_at)).order_by(func.date(Lesson.scheduled_at))
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)

    if from_date is not None:
        stmt = stmt.where(Lesson.scheduled_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Lesson.scheduled_at <= to_date)
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


async def reminders_daily_stats(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> list[tuple[str, int]]:
    """Get daily reminder instance counts with optional date range.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        from_date: Optional start date filter
        to_date: Optional end date filter
        
    Returns:
        List of tuples (date_string, count) ordered by date
    """
    stmt = select(func.date(ReminderInstance.scheduled_for), func.count()).group_by(func.date(ReminderInstance.scheduled_for)).order_by(func.date(ReminderInstance.scheduled_for))
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)

    if from_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for >= from_date)
    if to_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for <= to_date)
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


# ============================================================================
# Tenant CRUD Operations
# ============================================================================


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    contact_email: Optional[str] = None,
    is_active: bool = True,
) -> Tenant:
    """Create new tenant.
    
    Args:
        session: Async database session
        name: Tenant name
        slug: URL-friendly unique identifier
        contact_email: Contact email
        is_active: Whether tenant is active
        
    Returns:
        Created Tenant object
    """
    now = datetime.now(timezone.utc)
    tenant = Tenant(
        name=name,
        slug=slug,
        contact_email=contact_email,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)
    return tenant


async def get_tenant(session: AsyncSession, tenant_id: int) -> Tenant | None:
    """Get tenant by ID.
    
    Args:
        session: Async database session
        tenant_id: Tenant ID
        
    Returns:
        Tenant object or None
    """
    return await session.get(Tenant, tenant_id)


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    """Get tenant by slug.
    
    Args:
        session: Async database session
        slug: Tenant slug
        
    Returns:
        Tenant object or None
    """
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_tenants(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Tenant], int]:
    """List all tenants with pagination.
    
    Args:
        session: Async database session
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        Tuple of (list of Tenant objects, total count)
    """
    stmt = select(Tenant).order_by(Tenant.name.asc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    total = (await session.execute(select(func.count()).select_from(Tenant))).scalar_one()
    return result.scalars().all(), total


async def update_tenant(
    session: AsyncSession,
    tenant: Tenant,
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    contact_email: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Tenant:
    """Update tenant fields.
    
    Args:
        session: Async database session
        tenant: Tenant object to update
        name: New name
        slug: New slug
        contact_email: New contact email
        is_active: New active status
        
    Returns:
        Updated Tenant object
    """
    if name is not None:
        tenant.name = name
    if slug is not None:
        tenant.slug = slug
    if contact_email is not None:
        tenant.contact_email = contact_email
    if is_active is not None:
        tenant.is_active = is_active
    tenant.updated_at = datetime.now(timezone.utc)
    session.add(tenant)
    return tenant


async def delete_tenant(session: AsyncSession, tenant: Tenant) -> None:
    """Delete tenant.
    
    Cascades to delete all related data (users, learners, packages, lessons, reminders).
    
    Args:
        session: Async database session
        tenant: Tenant object to delete
    """
    await session.delete(tenant)



# ============================================================================
# InviteToken CRUD Operations
# ============================================================================


async def create_invite_token(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    created_by_user_id: int,
    expires_in_days: int = 30,
) -> InviteToken:
    """Create new invite token for tenant.
    
    Generates cryptographically secure token for user registration.
    Super-admins cannot create tokens (must be tenant-specific).
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        created_by_user_id: User creating the token
        expires_in_days: Token validity period (default: 30 days)
        
    Returns:
        Created InviteToken object
        
    Raises:
        HTTPException: If super-admin attempts to create token
    """
    import secrets
    from datetime import timedelta
    
    if current_tenant.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admins cannot create invite tokens"
        )
    
    # Generate cryptographically secure token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    
    invite_token = InviteToken(
        tenant_id=current_tenant.tenant_id,
        token=token,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    
    session.add(invite_token)
    await session.flush()
    return invite_token


async def get_invite_token_by_token(
    session: AsyncSession,
    token: str,
) -> Optional[InviteToken]:
    """Get invite token by token string.
    
    No tenant filtering - needed for registration flow.
    Eager loads tenant and created_by relationships.
    
    Args:
        session: Async database session
        token: Token string to lookup
        
    Returns:
        InviteToken object with relationships loaded or None
    """
    stmt = (
        select(InviteToken)
        .options(
            selectinload(InviteToken.tenant),
            selectinload(InviteToken.created_by)
        )
        .where(InviteToken.token == token)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_invite_token_as_used(
    session: AsyncSession,
    invite_token: InviteToken,
) -> InviteToken:
    """Mark invite token as used.
    
    Sets used_at timestamp to current UTC time.
    
    Args:
        session: Async database session
        invite_token: InviteToken object to mark as used
        
    Returns:
        Updated InviteToken object
    """
    invite_token.used_at = datetime.now(timezone.utc)
    await session.flush()
    return invite_token


async def list_invite_tokens(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InviteToken], int]:
    """List invite tokens for tenant with pagination.
    
    Super-admins cannot list tokens (must be tenant-specific).
    Eager loads created_by relationship.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        Tuple of (list of InviteToken objects, total count)
        
    Raises:
        HTTPException: If super-admin attempts to list tokens
    """
    if current_tenant.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admins cannot list invite tokens"
        )
    
    # Count query
    count_query = select(func.count()).select_from(InviteToken)
    count_query = count_query.where(InviteToken.tenant_id == current_tenant.tenant_id)
    total = (await session.execute(count_query)).scalar_one()
    
    if total == 0:
        return [], 0
    
    # Data query
    stmt = (
        select(InviteToken)
        .options(
            selectinload(InviteToken.created_by)
        )
        .where(InviteToken.tenant_id == current_tenant.tenant_id)
        .order_by(InviteToken.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    tokens = result.scalars().all()
    return tokens, total


# ============================================================================
# Test Reminders CRUD Operations
# ============================================================================


async def fetch_packages_with_active_reminders(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
) -> tuple[list[LessonPackage], int]:
    """Fetch lesson packages that have active reminder instances.
    
    Returns packages with at least one active reminder (status='scheduled', active=True).
    Eager loads learner and bot_user for display. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        Tuple of (list of LessonPackage objects, total count)
    """
    # Subquery to find package IDs with active reminders
    active_reminders_subquery = (
        select(ReminderInstance.package_id)
        .where(
            and_(
                ReminderInstance.status == 'scheduled',
                ReminderInstance.active == True
            )
        )
        .distinct()
    )
    
    if current_tenant.tenant_id is not None:
        active_reminders_subquery = active_reminders_subquery.where(
            ReminderInstance.tenant_id == current_tenant.tenant_id
        )
    
    # Base query for packages with active reminders
    base_query = select(LessonPackage).where(
        LessonPackage.id.in_(active_reminders_subquery)
    )
    
    if current_tenant.tenant_id is not None:
        base_query = base_query.where(LessonPackage.tenant_id == current_tenant.tenant_id)
    
    # Count query
    count_stmt = base_query.with_only_columns(func.count()).order_by(None)
    total = (await session.execute(count_stmt)).scalar_one()
    
    if total == 0:
        return [], 0
    
    # Data query with eager loading
    rows_stmt = (
        base_query.options(
            joinedload(LessonPackage.learner).joinedload(Learner.bot_user),
            joinedload(LessonPackage.template),
        )
        .order_by(LessonPackage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    rows = (await session.execute(rows_stmt)).scalars().all()
    return rows, total


async def fetch_active_reminders_for_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
) -> list[ReminderInstance]:
    """Fetch all active reminder instances for specific package.
    
    Returns only reminders with status='scheduled' and active=True.
    Eager loads rule, package, learner, and lesson.
    Orders by scheduled time ascending. Applies tenant filtering.
    
    Args:
        session: Async database session
        current_tenant: Current tenant context for filtering
        package_id: Package ID
        
    Returns:
        List of active ReminderInstance objects for the package
    """
    stmt = (
        select(ReminderInstance)
        .options(
            selectinload(ReminderInstance.rule),
            selectinload(ReminderInstance.package),
            selectinload(ReminderInstance.learner),
            selectinload(ReminderInstance.lesson),
        )
        .where(
            and_(
                ReminderInstance.package_id == package_id,
                ReminderInstance.status == 'scheduled',
                ReminderInstance.active == True
            )
        )
        .order_by(ReminderInstance.scheduled_for.asc())
    )
    
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)
    
    return (await session.execute(stmt)).scalars().all()
