import pytest
from datetime import datetime, timezone, timedelta

from aiogram.types import User as AiogramUser
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from tests import factories


def _mk_application():
    now = datetime.now(timezone.utc)
    return {
        "created_at": now,
        "name": "John Doe",
        "language": "en",
        "level": "B1",
        "preferred_time": "Mon 10:00",
        "contact": "@john",
    }


@pytest.mark.asyncio
async def test_applications_crud(db_session: AsyncSession):
    await crud.add_application(db_session, _mk_application())
    await crud.add_application(db_session, _mk_application())
    await db_session.flush()

    all_apps = await crud.fetch_all_applications(db_session)
    assert len(all_apps) == 2

    last_one = await crud.fetch_last_n_applications(db_session, 1)
    assert len(last_one) == 1

    total = await crud.fetch_applications_count(db_session)
    assert total == 2

    stats = await crud.fetch_applications_stats(db_session)
    assert stats["total"] == 2
    assert "en" in stats["by_language"]

    await crud.delete_all_applications(db_session)
    remaining = await crud.fetch_all_applications(db_session)
    assert remaining == []


@pytest.mark.asyncio
async def test_students_crud(db_session: AsyncSession):
    await crud.add_student(db_session, "Alice", "Story", "file_123")
    await db_session.flush()
    students = await crud.get_all_students(db_session)
    assert students[0].name == "Alice"

    student = await crud.get_student(db_session, students[0].id)
    assert student.story == "Story"

    await crud.delete_student(db_session, student.id)
    await db_session.flush()
    assert await crud.get_student(db_session, student.id) is None


@pytest.mark.asyncio
async def test_bot_user_upsert_and_fetch(db_session: AsyncSession):
    aiogram_user = AiogramUser(
        id=123,
        is_bot=False,
        first_name="Bot",
        username="botuser",
    )
    bot_user = await crud.upsert_bot_user(db_session, aiogram_user)
    assert bot_user.chat_id == 123

    # second call updates
    aiogram_user_updated = AiogramUser(
        id=123,
        is_bot=False,
        first_name="Bot",
        username="updated",
    )
    bot_user2 = await crud.upsert_bot_user(db_session, aiogram_user_updated)
    assert bot_user2.username == "updated"

    # available bot users
    available, total = await crud.fetch_available_bot_users(db_session, limit=10, offset=0, search="upd")
    assert total == 1
    assert available[0].chat_id == 123


@pytest.mark.asyncio
async def test_learners_crud(db_session: AsyncSession):
    bot_user = await factories.create_bot_user(db_session, chat_id=321)
    learner = await crud.create_learner(
        db_session,
        bot_user_id=bot_user.id,
        display_name="Learner One",
        notes="Note",
    )
    await db_session.flush()

    fetched = await crud.get_learner(db_session, learner.id)
    assert fetched.display_name == "Learner One"

    await crud.update_learner(db_session, fetched, notifications_enabled=False)
    await db_session.flush()
    refreshed = await crud.get_learner(db_session, learner.id)
    assert refreshed.notifications_enabled is False

    # create from chat id reuses bot user
    learner2 = await crud.create_learner_from_chat_id(
        db_session,
        chat_id=321,
        display_name="Learner Two",
    )
    assert learner2.id == learner.id  # same learner

    all_learners = await crud.fetch_all_learners(db_session)
    assert len(all_learners) == 1

    paginated, total = await crud.fetch_learners_paginated(db_session, limit=10, offset=0)
    assert total == 1
    assert paginated[0].display_name == "Learner One"


@pytest.mark.asyncio
async def test_template_crud(db_session: AsyncSession):
    template = await crud.create_lesson_package_template(
        db_session,
        name="Template",
        description="Desc",
        lesson_count=5,
        duration_days=10,
        default_timezone="Europe/Moscow",
        default_config={"weekly_schedule": []},
    )
    await db_session.flush()

    fetched = await crud.get_lesson_package_template(db_session, template.id)
    assert fetched.lesson_count == 5

    await crud.update_lesson_package_template(db_session, fetched, name="Updated")
    await db_session.flush()

    assert (await crud.get_lesson_package_template(db_session, template.id)).name == "Updated"

    templates = await crud.fetch_lesson_package_templates(db_session)
    assert len(templates) == 1

    await crud.delete_lesson_package_template(db_session, fetched)
    await db_session.flush()

    assert await crud.get_lesson_package_template(db_session, template.id) is None


@pytest.mark.asyncio
async def test_lesson_package_crud(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await crud.create_lesson_package(
        db_session,
        learner=learner,
        title="Package",
        status="draft",
        timezone_name="Europe/Moscow",
    )
    await db_session.flush()

    fetched = await crud.get_lesson_package(db_session, package.id)
    assert fetched.title == "Package"

    packages, total = await crud.fetch_lesson_packages_paginated(
        db_session,
        limit=10,
        offset=0,
        learner_id=learner.id,
    )
    assert total == 1
    assert packages[0].learner_id == learner.id

    await crud.delete_lesson_package(db_session, fetched)
    await db_session.flush()
    assert await crud.get_lesson_package(db_session, package.id) is None


@pytest.mark.asyncio
async def test_lesson_crud(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await crud.create_lesson(
        db_session,
        package,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )
    await db_session.flush()

    fetched = await crud.get_lesson(db_session, lesson.id)
    assert fetched.status == "scheduled"

    lessons = await crud.fetch_lessons_for_package(db_session, package.id)
    assert len(lessons) == 1

    all_lessons, total = await crud.list_all_lessons(db_session, limit=10, offset=0)
    assert total == 1
    assert all_lessons[0].id == lesson.id

    await crud.delete_lesson(db_session, fetched)
    await db_session.flush()
    assert await crud.get_lesson(db_session, lesson.id) is None


@pytest.mark.asyncio
async def test_reminder_rules_and_instances(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)

    rule = await crud.create_reminder_rule(
        db_session,
        package=package,
        lesson=lesson,
        reminder_type="lesson",
        config={},
    )
    await db_session.flush()

    scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
    instance = await crud.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson,
        scheduled_for=scheduled_for,
    )
    await db_session.flush()

    due = await crud.fetch_reminder_instances_due(db_session, datetime.now(timezone.utc))
    assert due

    paginated, total = await crud.fetch_reminder_instances_paginated(db_session, limit=10, offset=0)
    assert total == 1
    assert paginated[0].id == instance.id

    await crud.set_reminder_instance_status(
        db_session,
        instance,
        status="sent",
        active=False,
        comment="Done",
    )
    await db_session.flush()

    refreshed = await crud.get_reminder_instance(db_session, instance.id)
    assert refreshed.status == "sent"


@pytest.mark.asyncio
async def test_stats_helpers(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await factories.create_lesson(db_session, package=package, status="completed")
    await factories.create_lesson(db_session, package=package, status="scheduled")

    rule = await factories.create_reminder_rule(db_session, package=package)
    await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        status="delivered",
    )
    await db_session.flush()

    lessons_stats = await crud.count_lessons_by_status(db_session)
    assert lessons_stats["completed"] == 1

    reminders_stats = await crud.count_reminders_by_status(db_session)
    assert reminders_stats["delivered"] == 1

    daily_lessons = await crud.lessons_daily_stats(db_session)
    assert daily_lessons

    daily_reminders = await crud.reminders_daily_stats(db_session)
    assert daily_reminders


@pytest.mark.asyncio
async def test_user_crud(db_session: AsyncSession):
    user = await crud.create_user(
        db_session,
        telegram_id=999,
        username="user",
        display_name="User",
        role="viewer",
    )
    await db_session.flush()

    fetched = await crud.get_user(db_session, user.id)
    assert fetched.display_name == "User"

    await crud.update_user_login_metadata(db_session, fetched, role="teacher")
    await db_session.flush()
    assert (await crud.get_user(db_session, user.id)).role == "teacher"

    users = await crud.list_users(db_session)
    assert len(users) == 1


@pytest.mark.asyncio
async def test_create_user_invalid_role(db_session: AsyncSession):
    with pytest.raises(ValueError):
        await crud.create_user(
            db_session,
            telegram_id=1,
            username="bad",
            display_name="Bad",
            role="invalid",
        )


@pytest.mark.asyncio
async def test_create_user_invalid_telegram_id(db_session: AsyncSession):
    with pytest.raises(ValueError):
        await crud.create_user(
            db_session,
            telegram_id=-1,
            username="bad",
            display_name="User",
            role="viewer",
        )


@pytest.mark.asyncio
async def test_create_learner_from_chat_id_invalid(db_session: AsyncSession):
    with pytest.raises(ValueError):
        await crud.create_learner_from_chat_id(
            db_session,
            chat_id=0,
            display_name="Invalid",
        )


@pytest.mark.asyncio
async def test_create_lesson_package_invalid_timezone(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    with pytest.raises(ValueError):
        await crud.create_lesson_package(
            db_session,
            learner=learner,
            title="Bad",
            status="draft",
            timezone_name="Bad/Zone",
        )


@pytest.mark.asyncio
async def test_create_lesson_invalid_status(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    with pytest.raises(ValueError):
        await crud.create_lesson(
            db_session,
            package,
            scheduled_at=datetime.now(timezone.utc),
            status="bad",
        )


@pytest.mark.asyncio
async def test_fetch_lesson_packages_paginated_search(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    await factories.create_package(db_session, learner=learner, title="Alpha")
    result, total = await crud.fetch_lesson_packages_paginated(
        db_session,
        limit=10,
        offset=0,
        search="Beta",
    )
    assert total == 0
    assert result == []


@pytest.mark.asyncio
async def test_fetch_reminder_instances_paginated_search(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        status="scheduled",
        payload={"student_name": "Tester"},
    )
    await db_session.flush()

    result, total = await crud.fetch_reminder_instances_paginated(
        db_session,
        limit=10,
        offset=0,
        search="NoMatch",
    )
    assert total == 0
    assert result == []
