import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from services import lesson_service
from services.exceptions import NotFoundError
from services.reminder_definitions import REMINDER_TYPE_PACKAGE_RENEWAL
from database import crud
from tests import factories


@pytest.mark.asyncio
async def test_create_and_get_lesson(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, display_name="Service Student")
    package = await factories.create_package(db_session, learner=learner)
    await db_session.flush()
    scheduled = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)

    dto = await lesson_service.create_lesson(
        db_session,
        current_tenant,
        package_id=package.id,
        scheduled_at=scheduled,
        duration_minutes=45,
        status="scheduled",
        teacher_notes="Initial lesson",
        sequence_index=1,
    )

    assert dto.package_id == package.id
    assert dto.duration_minutes == 45
    assert dto.sequence_index == 1

    fetched = await lesson_service.get_lesson(db_session, current_tenant, dto.id)
    assert fetched.id == dto.id
    assert fetched.package_title == package.title


@pytest.mark.asyncio
async def test_create_lesson_missing_package_raises(db_session: AsyncSession, current_tenant: CurrentTenant):
    scheduled = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(NotFoundError):
        await lesson_service.create_lesson(
            db_session,
            current_tenant,
            package_id=999,
            scheduled_at=scheduled,
        )


@pytest.mark.asyncio
async def test_create_lesson_keeps_flexible_package_allowance_and_does_not_create_renewal(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, chat_id=123456)
    package = await factories.create_package(
        db_session,
        learner=learner,
        status="active",
        total_lessons=8,
    )
    package.end_date = None
    original_start = package.start_date
    await db_session.flush()

    await lesson_service.create_lesson(
        db_session,
        current_tenant,
        package_id=package.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    assert refreshed.total_lessons == 8
    assert refreshed.start_date == original_start
    assert refreshed.end_date is None
    assert refreshed.status == "active"
    assert REMINDER_TYPE_PACKAGE_RENEWAL not in {
        rule.reminder_type for rule in refreshed.reminder_rules
    }


@pytest.mark.asyncio
async def test_update_lesson(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc),
    )
    await db_session.flush()

    dto = await lesson_service.update_lesson(
        db_session,
        current_tenant,
        lesson_id=lesson.id,
        status="completed",
        duration_minutes=80,
        teacher_notes="Done",
    )

    assert dto.status == "completed"
    assert dto.duration_minutes == 80
    assert dto.teacher_notes == "Done"


@pytest.mark.asyncio
async def test_update_lesson_missing_raises(db_session: AsyncSession, current_tenant: CurrentTenant):
    with pytest.raises(NotFoundError):
        await lesson_service.update_lesson(db_session, current_tenant, lesson_id=999, status="completed")


@pytest.mark.asyncio
async def test_delete_lesson(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)
    await db_session.flush()

    await lesson_service.delete_lesson(db_session, current_tenant, lesson.id)
    with pytest.raises(NotFoundError):
        await lesson_service.get_lesson(db_session, current_tenant, lesson.id)


@pytest.mark.asyncio
async def test_list_lessons(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await factories.create_lesson(db_session, package=package, sequence_index=1)
    await factories.create_lesson(db_session, package=package, sequence_index=2)
    await db_session.flush()

    lessons = await lesson_service.list_lessons(db_session, current_tenant, package.id)
    assert len(lessons) == 2
    assert {lesson.sequence_index for lesson in lessons} == {1, 2}


@pytest.mark.asyncio
async def test_list_all_lessons(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, display_name="Global Student")
    package = await factories.create_package(db_session, learner=learner, title="Global Package", status="active")
    await factories.create_lesson(db_session, package=package, sequence_index=1)
    await db_session.flush()

    lessons, total = await lesson_service.list_all_lessons(
        db_session,
        current_tenant,
        search="Global",
        limit=10,
        offset=0,
    )
    assert total == 1
    assert lessons[0].package_title == "Global Package"
