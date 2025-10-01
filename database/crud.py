from datetime import datetime, timezone
from typing import Optional

from aiogram.types import User
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Application, Student, LessonReminder, BotUser, Learner


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
    reminder = LessonReminder(**reminder_data)
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


# --- Bot users & learners ---------------------------------------------------


async def upsert_bot_user(session: AsyncSession, user: User) -> BotUser:
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
