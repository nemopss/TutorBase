from datetime import datetime, timezone
from typing import Optional

from aiogram.types import User as AiogramUser
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    Application,
    Student,
    LessonReminder,
    BotUser,
    Learner,
    LessonPackageTemplate,
    LessonPackage,
    Lesson,
    ReminderRule,
    ReminderInstance,
    User,
)


async def add_application(session: AsyncSession, app_data: dict):
    new_app = Application(**app_data)
    session.add(new_app)


async def fetch_last_n_applications(session: AsyncSession, n: int = 20):
    query = select(Application).order_by(Application.id.desc()).limit(n)
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_all_applications(session: AsyncSession):
    query = select(Application).order_by(Application.id.asc())
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_applications_count(session: AsyncSession):
    query = select(func.count()).select_from(Application)
    result = await session.execute(query)
    return result.scalar_one()


async def fetch_applications_stats(session: AsyncSession) -> dict:
    """Return aggregate statistics for applications."""
    total_query = select(func.count()).select_from(Application)
    total = (await session.execute(total_query)).scalar_one()

    by_language_query = (
        select(Application.language, func.count())
        .group_by(Application.language)
    )
    by_language_result = await session.execute(by_language_query)
    by_language = {lang or '—': count for lang, count in by_language_result.all()}

    by_month_query = (
        select(func.strftime('%Y-%m', Application.created_at).label('month'), func.count())
        .group_by('month')
        .order_by('month')
    )
    by_month_result = await session.execute(by_month_query)
    by_month = {month or '—': count for month, count in by_month_result.all()}

    recent_query = (
        select(Application)
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


async def delete_all_applications(session: AsyncSession):
    query = select(Application)
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


async def create_lesson_reminder(session: AsyncSession, reminder_data: dict) -> LessonReminder:
    payload = dict(reminder_data)
    payload.setdefault('kind', 'lesson')
    reminder = LessonReminder(**payload)
    session.add(reminder)
    await session.flush([reminder])
    return reminder


async def get_lesson_reminders(session: AsyncSession, include_inactive: bool = True) -> list[LessonReminder]:
    query = select(LessonReminder)
    if not include_inactive:
        query = query.where(LessonReminder.active.is_(True))
    query = query.order_by(LessonReminder.student_name.asc())
    result = await session.execute(query)
    return result.scalars().all()


async def get_lesson_reminder(session: AsyncSession, reminder_id: int) -> LessonReminder | None:
    return await session.get(LessonReminder, reminder_id)


async def save_lesson_reminder(session: AsyncSession, reminder: LessonReminder) -> None:
    session.add(reminder)


async def delete_lesson_reminder(session: AsyncSession, reminder: LessonReminder) -> None:
    await session.delete(reminder)


async def fetch_due_reminders(session: AsyncSession, now_utc: datetime) -> list[LessonReminder]:
    query = select(LessonReminder).where(
        LessonReminder.active.is_(True),
        LessonReminder.next_run_at <= now_utc
    )
    result = await session.execute(query)
    return result.scalars().all()


async def fetch_reminders_stats(session: AsyncSession) -> tuple[int, int]:
    total_stmt = select(func.count()).select_from(LessonReminder)
    active_stmt = (
        select(func.count())
        .select_from(LessonReminder)
        .where(LessonReminder.active.is_(True))
    )
    total = (await session.execute(total_stmt)).scalar_one()
    active = (await session.execute(active_stmt)).scalar_one()
    return active, total


# --- Users ------------------------------------------------------------------


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int | None,
    username: str | None,
    display_name: str,
    role: str = "teacher",
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
        role=role,
        created_at=now,
        updated_at=now,
        last_login_at=now,
    )
    session.add(user)
    await session.flush([user])
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
    await session.flush([user])
    return user


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
        await session.flush([existing])
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
    await session.flush([new_bot_user])
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
    *,
    limit: int,
    offset: int,
) -> tuple[list[Learner], int]:
    total_stmt = select(func.count()).select_from(Learner)
    total = (await session.execute(total_stmt)).scalar_one()

    if total == 0:
        return [], 0

    rows_stmt = (
        select(Learner)
        .options(selectinload(Learner.bot_user))
        .order_by(Learner.display_name.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()
    return rows, total


async def create_learner(
    session: AsyncSession,
    *,
    bot_user_id: int,
    display_name: str,
    notes: Optional[str] = None,
) -> Learner:
    now_utc = datetime.now(timezone.utc)
    learner = Learner(
        bot_user_id=bot_user_id,
        display_name=display_name,
        notes=notes,
        created_at=now_utc,
    )
    session.add(learner)
    await session.flush([learner])
    return learner


async def get_bot_user(session: AsyncSession, bot_user_id: int) -> BotUser | None:
    return await session.get(BotUser, bot_user_id)


async def get_bot_user_by_chat_id(session: AsyncSession, chat_id: int) -> BotUser | None:
    stmt = select(BotUser).where(BotUser.chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner(session: AsyncSession, learner_id: int) -> Learner | None:
    stmt = select(Learner).options(selectinload(Learner.bot_user)).where(Learner.id == learner_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_learner_by_bot_user(session: AsyncSession, bot_user_id: int) -> Learner | None:
    stmt = select(Learner).where(Learner.bot_user_id == bot_user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_learner(
    session: AsyncSession,
    learner: Learner,
    *,
    display_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> Learner:
    if display_name is not None:
        learner.display_name = display_name
    learner.notes = notes
    session.add(learner)
    await session.flush([learner])
    return learner


async def delete_learner(session: AsyncSession, learner: Learner) -> None:
    await session.delete(learner)


# --- Lesson packages & lessons ---------------------------------------------


async def create_lesson_package_template(
    session: AsyncSession,
    *,
    name: str,
    description: Optional[str] = None,
    lesson_count: Optional[int] = None,
    duration_days: Optional[int] = None,
    default_timezone: str = "Europe/Moscow",
    default_config: Optional[dict] = None,
) -> LessonPackageTemplate:
    template = LessonPackageTemplate(
        name=name,
        description=description,
        lesson_count=lesson_count,
        duration_days=duration_days,
        default_timezone=default_timezone,
        default_config=default_config or {},
    )
    session.add(template)
    await session.flush([template])
    return template


async def get_lesson_package_template(session: AsyncSession, template_id: int) -> LessonPackageTemplate | None:
    return await session.get(LessonPackageTemplate, template_id)


async def fetch_lesson_package_templates(session: AsyncSession) -> list[LessonPackageTemplate]:
    stmt = select(LessonPackageTemplate).order_by(LessonPackageTemplate.name.asc())
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
    await session.flush([template])
    return template


async def delete_lesson_package_template(session: AsyncSession, template: LessonPackageTemplate) -> None:
    await session.delete(template)


async def create_lesson_package(
    session: AsyncSession,
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
) -> LessonPackage:
    package = LessonPackage(
        learner=learner,
        template=template,
        title=title,
        status=status,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone_name or (template.default_timezone if template else "Europe/Moscow"),
        total_lessons=total_lessons,
        notes=notes,
    )
    session.add(package)
    await session.flush([package])
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
    await session.flush([package])
    return package


async def get_lesson_package(session: AsyncSession, package_id: int) -> LessonPackage | None:
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
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_lesson_packages_for_learner(
    session: AsyncSession,
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
    return (await session.execute(stmt)).scalars().all()


async def create_lesson(
    session: AsyncSession,
    package: LessonPackage,
    *,
    scheduled_at: datetime,
    duration_minutes: Optional[int] = None,
    status: str = "scheduled",
    sequence_index: Optional[int] = None,
    teacher_notes: Optional[str] = None,
    homework_due_at: Optional[datetime] = None,
) -> Lesson:
    lesson = Lesson(
        package=package,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        status=status,
        sequence_index=sequence_index,
        teacher_notes=teacher_notes,
        homework_due_at=homework_due_at,
    )
    session.add(lesson)
    await session.flush([lesson])
    return lesson


async def get_lesson(session: AsyncSession, lesson_id: int) -> Lesson | None:
    stmt = (
        select(Lesson)
        .options(
            selectinload(Lesson.package),
            selectinload(Lesson.reminder_rules),
        )
        .where(Lesson.id == lesson_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_lesson(session: AsyncSession, lesson: Lesson) -> None:
    await session.delete(lesson)


async def fetch_lesson_packages_paginated(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[LessonPackage], int]:
    total_stmt = select(func.count()).select_from(LessonPackage)
    total = (await session.execute(total_stmt)).scalar_one()
    if total == 0:
        return [], 0

    rows_stmt = (
        select(LessonPackage)
        .options(
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


async def fetch_lessons_for_package(session: AsyncSession, package_id: int) -> list[Lesson]:
    stmt = (
        select(Lesson)
        .options(selectinload(Lesson.package))
        .where(Lesson.package_id == package_id)
        .order_by(Lesson.sequence_index.asc().nulls_last(), Lesson.scheduled_at.asc())
    )
    return (await session.execute(stmt)).scalars().all()


# --- Reminder rules & instances -------------------------------------------


async def create_reminder_rule(
    session: AsyncSession,
    *,
    package: LessonPackage,
    lesson: Lesson | None,
    reminder_type: str,
    config: Optional[dict] = None,
    channel: str = "telegram",
    active: bool = True,
) -> ReminderRule:
    rule = ReminderRule(
        package=package,
        lesson=lesson,
        reminder_type=reminder_type,
        config=config or {},
        channel=channel,
        active=active,
    )
    session.add(rule)
    await session.flush([rule])
    return rule


async def get_reminder_rule(session: AsyncSession, rule_id: int) -> ReminderRule | None:
    stmt = select(ReminderRule).where(ReminderRule.id == rule_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_reminder_instance(
    session: AsyncSession,
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
) -> ReminderInstance:
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
    )
    session.add(instance)
    await session.flush([instance])
    return instance


async def fetch_reminder_instances_due(
    session: AsyncSession,
    now_utc: datetime,
    *,
    statuses: Optional[list[str]] = None,
) -> list[ReminderInstance]:
    if statuses is None:
        statuses = ["scheduled"]
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
    await session.flush([instance])
    return instance


async def get_reminder_instance(session: AsyncSession, instance_id: int) -> ReminderInstance | None:
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
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_reminder_instances_for_package(
    session: AsyncSession,
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
    return (await session.execute(stmt)).scalars().all()


async def fetch_reminder_instances_count(
    session: AsyncSession,
    status: Optional[str] = None,
) -> int:
    stmt = select(func.count()).select_from(ReminderInstance)
    if status is not None:
        stmt = stmt.where(ReminderInstance.status == status)
    result = await session.execute(stmt)
    return result.scalar_one()


async def count_lessons_by_status(session: AsyncSession) -> dict[str, int]:
    stmt = select(Lesson.status, func.count()).group_by(Lesson.status)
    result = await session.execute(stmt)
    return {status or 'unknown': count for status, count in result.all()}


async def count_reminders_by_status(session: AsyncSession) -> dict[str, int]:
    stmt = select(ReminderInstance.status, func.count()).group_by(ReminderInstance.status)
    result = await session.execute(stmt)
    return {status or 'unknown': count for status, count in result.all()}


async def lessons_daily_stats(
    session: AsyncSession,
    *,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> list[tuple[str, int]]:
    stmt = select(func.date(Lesson.scheduled_at), func.count()).group_by(func.date(Lesson.scheduled_at)).order_by(func.date(Lesson.scheduled_at))
    if from_date is not None:
        stmt = stmt.where(Lesson.scheduled_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Lesson.scheduled_at <= to_date)
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


async def reminders_daily_stats(
    session: AsyncSession,
    *,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> list[tuple[str, int]]:
    stmt = select(func.date(ReminderInstance.scheduled_for), func.count()).group_by(func.date(ReminderInstance.scheduled_for)).order_by(func.date(ReminderInstance.scheduled_for))
    if from_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for >= from_date)
    if to_date is not None:
        stmt = stmt.where(ReminderInstance.scheduled_for <= to_date)
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]
