from __future__ import annotations
from datetime import datetime, timezone, date
from email.mime import base
from typing import Optional, TYPE_CHECKING

from aiogram.types import User as AiogramUser
from sqlalchemy import select, func, or_, and_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from api.dependencies import CurrentTenant

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
from database.validators import (
    ensure_positive_int,
    ensure_non_empty,
    ensure_valid_timezone,
    ensure_in_list,
    ensure_positive_int_or_none,
)


async def add_application(session: AsyncSession, current_tenant: CurrentTenant, app_data: dict, tenant_id: Optional[int] = None):
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

    new_app = Application(**app_data, tenant_id=final_tenant_id)
    session.add(new_app)


async def fetch_last_n_applications(session: AsyncSession, current_tenant: CurrentTenant, n: int = 20):
    query = select(Application).order_by(Application.id.desc())
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    query = query.limit(n)
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_all_applications(session: AsyncSession, current_tenant: CurrentTenant):
    query = select(Application).order_by(Application.id.asc())
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_applications_count(session: AsyncSession, current_tenant: CurrentTenant):
    query = select(func.count()).select_from(Application)
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    result = await session.execute(query)
    return result.scalar_one()


async def fetch_applications_stats(session: AsyncSession, current_tenant: CurrentTenant) -> dict:
    """Return aggregate statistics for applications."""
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
    """
    DANGEROUS: Delete all applications. Only super-admins can delete across all tenants.
    Regular users can only delete from their own tenant.
    """
    query = select(Application)
    if current_tenant.tenant_id is not None:
        query = query.where(Application.tenant_id == current_tenant.tenant_id)
    
    result = await session.execute(query)
    for app in result.scalars().all():
        await session.delete(app)


async def add_student(session: AsyncSession, name: str, story: str, photo_file_id: str | None = None):
    new_student = Student(name=name, story=story, photo_file_id=photo_file_id)
    session.add(new_student)


async def get_all_students(session: AsyncSession):
    query = select(Student).order_by(Student.name)
    result = await session.execute(query)
    return result.scalars().all()


async def get_student(session: AsyncSession, student_id: int):
    return await session.get(Student, student_id)


async def delete_student(session: AsyncSession, student_id: int):
    student = await session.get(Student, student_id)
    if student:
        await session.delete(student)


# --- Users ------------------------------------------------------------------


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
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
    # Validation
    VALID_ROLES = ["viewer", "teacher", "admin"]
    
    display_name = ensure_non_empty(display_name, "display_name", max_len=255)
    role = ensure_in_list(role, "role", VALID_ROLES)
    
    if telegram_id is not None:
        telegram_id = ensure_positive_int(telegram_id, "telegram_id")

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
    now = datetime.now(timezone.utc)
    if username is not None:
        user.username = username
    if display_name is not None:
        user.display_name = display_name
    if role is not None:
        user.role = role
    if last_login_at is not None:
        user.last_login_at = last_login_at
    else:
        user.last_login_at = now
    user.updated_at = now
    session.add(user)
    return user


async def list_users(session: AsyncSession, current_tenant: CurrentTenant) -> list[User]:
    stmt = select(User).order_by(User.created_at.asc())
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(User.tenant_id == current_tenant.tenant_id)
    result = await session.execute(stmt)
    return result.scalars().all()


# --- Bot users & learners ---------------------------------------------------


async def upsert_bot_user(session: AsyncSession, user: AiogramUser) -> BotUser:
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
    base_query = select(BotUser).outerjoin(Learner).where(Learner.id.is_(None))

    if search:
        pattern = f"%{search.lower()}%"
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


async def fetch_learners_paginated(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Learner], int]:
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
    now_utc = datetime.now(timezone.utc)

    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

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
    return await session.get(BotUser, bot_user_id)


async def get_bot_user_by_chat_id(session: AsyncSession, chat_id: int) -> BotUser | None:
    stmt = select(BotUser).where(BotUser.chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner(session: AsyncSession, current_tenant: CurrentTenant, learner_id: int) -> Learner | None:
    stmt = select(Learner).options(selectinload(Learner.bot_user)).where(Learner.id == learner_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Learner.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner_by_bot_user(session: AsyncSession, current_tenant: CurrentTenant, bot_user_id: int) -> Learner | None:
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
    """
    Update learner with tenant validation.
    Critical: Ensure the learner belongs to the current tenant context.
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
    """
    Delete learner with tenant validation.
    Critical: Ensure the learner belongs to the current tenant context.
    """
    # Security check: Ensure learner belongs to current tenant
    if not current_tenant.is_super_admin and learner.tenant_id != current_tenant.tenant_id:
        raise ValueError(f"Cannot delete learner {learner.id} - does not belong to tenant {current_tenant.tenant_id}")
    
    await session.delete(learner)


async def fetch_all_learners(session: AsyncSession, current_tenant: CurrentTenant) -> list[Learner]:
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
    """Create a learner directly from chat_id, creating BotUser if needed."""
    # Validation
    chat_id = ensure_positive_int(chat_id, "chat_id")
    display_name = ensure_non_empty(display_name, "display_name", max_len=255)
    
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
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

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


# --- Lesson packages & lessons ---------------------------------------------


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
    # Validation
    name = ensure_non_empty(name, "name", max_len=255)
    lesson_count = ensure_positive_int_or_none(lesson_count, "lesson_count")
    duration_days = ensure_positive_int_or_none(duration_days, "duration_days")
    default_timezone = ensure_valid_timezone(default_timezone, "default_timezone")

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
    stmt = select(LessonPackageTemplate).where(LessonPackageTemplate.id == template_id)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackageTemplate.tenant_id == current_tenant.tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_lesson_package_templates(session: AsyncSession, current_tenant: CurrentTenant) -> list[LessonPackageTemplate]:
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
    await session.delete(template)


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
    # Validation
    VALID_PACKAGE_STATUSES = ["draft", "active", "completed", "cancelled"]
    
    title = ensure_non_empty(title, "title", max_len=255)
    status = ensure_in_list(status, "status", VALID_PACKAGE_STATUSES)
    total_lessons = ensure_positive_int_or_none(total_lessons, "total_lessons")
    
    final_tz = timezone_name or (template.default_timezone if template else "Europe/Moscow")
    final_tz = ensure_valid_timezone(final_tz, "timezone")

    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id
    
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
    await session.delete(package)


async def update_lesson_package(
    session: AsyncSession,
    package: LessonPackage,
    **fields,
) -> LessonPackage:
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
    stmt = (
        select(LessonPackage)
        .options(
            selectinload(LessonPackage.learner).selectinload(Learner.bot_user),
            selectinload(LessonPackage.template),
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
    stmt = (
        select(LessonPackage)
        .options(
            selectinload(LessonPackage.learner).selectinload(Learner.bot_user),
            selectinload(LessonPackage.template),
        )
        .where(LessonPackage.learner_id == learner_id)
        .order_by(LessonPackage.created_at.desc())
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(LessonPackage.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalars().all()


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
    # Validation
    VALID_LESSON_STATUSES = ["scheduled", "completed", "cancelled", "rescheduled"]
    
    status = ensure_in_list(status, "status", VALID_LESSON_STATUSES)
    duration_minutes = ensure_positive_int_or_none(duration_minutes, "duration_minutes")
    sequence_index = ensure_positive_int_or_none(sequence_index, "sequence_index")

    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id
    
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
    stmt = (
        select(Lesson)
        .options(
            selectinload(Lesson.package).selectinload(LessonPackage.learner),
            selectinload(Lesson.reminder_rules),
        )
        .where(Lesson.id == lesson_id)
    )
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_lesson(session: AsyncSession, lesson: Lesson) -> None:
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
    base_query = select(LessonPackage)
    if current_tenant.tenant_id is not None:
        base_query = base_query.where(LessonPackage.tenant_id == current_tenant.tenant_id)

    if learner_id is not None:
        base_query = base_query.where(LessonPackage.learner_id == learner_id)
    if status is not None:
        base_query = base_query.where(LessonPackage.status == status)
    if search:
        pattern = f"%{search}%"
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
            selectinload(LessonPackage.learner).selectinload(Learner.bot_user),
            selectinload(LessonPackage.template),
            selectinload(LessonPackage.lessons),
        )
        .order_by(LessonPackage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()
    return rows, total


async def fetch_lessons_for_package(session: AsyncSession, current_tenant: CurrentTenant, package_id: int) -> list[Lesson]:
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
    stmt = (
        select(Lesson)
        .options(
            selectinload(Lesson.package).selectinload(LessonPackage.learner),
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
            pattern = f"%{search_term.lower()}%"
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


# --- Reminder rules & instances -------------------------------------------


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
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

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
    if current_tenant.is_super_admin and tenant_id is not None:
        final_tenant_id = tenant_id
    else:
        final_tenant_id = current_tenant.tenant_id

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


async def get_reminder_instance(session: AsyncSession, current_tenant: CurrentTenant, instance_id: int) -> ReminderInstance | None:
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


async def fetch_reminder_instances_for_package(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    package_id: int,
) -> list[ReminderInstance]:
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


async def fetch_reminder_instances_count(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    status: Optional[str] = None,
) -> int:
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
        needs_package_join = True
        needs_learner_join = True
        # Search in comment, package title, and learner name
        search_pattern = f"%{search}%"
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


async def count_lessons_by_status(session: AsyncSession, current_tenant: CurrentTenant) -> dict[str, int]:
    stmt = select(Lesson.status, func.count()).group_by(Lesson.status)
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(Lesson.tenant_id == current_tenant.tenant_id)
    result = await session.execute(stmt)
    return {status or 'unknown': count for status, count in result.all()}


async def count_reminders_by_status(session: AsyncSession, current_tenant: CurrentTenant) -> dict[str, int]:
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
    stmt = select(func.date(ReminderInstance.scheduled_for), func.count()).group_by(func.date(ReminderInstance.scheduled_for)).order_by(func.date(ReminderInstance.scheduled_for))
    if current_tenant.tenant_id is not None:
        stmt = stmt.where(ReminderInstance.tenant_id == current_tenant.tenant_id)

    if from_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for >= from_date)
    if to_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for <= to_date)
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


# --- Tenants ----------------------------------------------------------------


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    contact_email: Optional[str] = None,
    is_active: bool = True,
) -> Tenant:
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
    return await session.get(Tenant, tenant_id)


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_tenants(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Tenant], int]:
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
    await session.delete(tenant)



# ============================================================================
# INVITE TOKEN OPERATIONS
# ============================================================================

async def create_invite_token(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    created_by_user_id: int,
    expires_in_days: int = 30,
) -> InviteToken:
    """Create a new invite token for a tenant."""
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
    """Get invite token by token string (no tenant filtering - needed for registration)."""
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
    """Mark an invite token as used."""
    invite_token.used_at = datetime.now(timezone.utc)
    await session.flush()
    return invite_token


async def list_invite_tokens(
    session: AsyncSession,
    current_tenant: CurrentTenant,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InviteToken], int]:
    """List invite tokens for a tenant."""
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
