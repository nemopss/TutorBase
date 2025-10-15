import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from services import lesson_service
from services.exceptions import NotFoundError
from tests import factories


@pytest.mark.asyncio
async def test_create_and_get_lesson(db_session: AsyncSession):
    learner = await factories.create_learner(db_session, display_name="Service Student")
    package = await factories.create_package(db_session, learner=learner)
    scheduled = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)

    dto = await lesson_service.create_lesson(
        db_session,
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

    fetched = await lesson_service.get_lesson(db_session, dto.id)
    assert fetched.id == dto.id
    assert fetched.package_title == package.title


@pytest.mark.asyncio
async def test_create_lesson_missing_package_raises(db_session: AsyncSession):
    scheduled = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(NotFoundError):
        await lesson_service.create_lesson(
            db_session,
            package_id=999,
            scheduled_at=scheduled,
        )


@pytest.mark.asyncio
async def test_update_lesson(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc),
    )

    dto = await lesson_service.update_lesson(
        db_session,
        lesson_id=lesson.id,
        status="completed",
        duration_minutes=80,
        teacher_notes="Done",
    )

    assert dto.status == "completed"
    assert dto.duration_minutes == 80
    assert dto.teacher_notes == "Done"


@pytest.mark.asyncio
async def test_update_lesson_missing_raises(db_session: AsyncSession):
    with pytest.raises(NotFoundError):
        await lesson_service.update_lesson(db_session, lesson_id=999, status="completed")


@pytest.mark.asyncio
async def test_delete_lesson(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)

    await lesson_service.delete_lesson(db_session, lesson.id)
    with pytest.raises(NotFoundError):
        await lesson_service.get_lesson(db_session, lesson.id)


@pytest.mark.asyncio
async def test_list_lessons(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await factories.create_lesson(db_session, package=package, sequence_index=1)
    await factories.create_lesson(db_session, package=package, sequence_index=2)

    lessons = await lesson_service.list_lessons(db_session, package.id)
    assert len(lessons) == 2
    assert {lesson.sequence_index for lesson in lessons} == {1, 2}


@pytest.mark.asyncio
async def test_list_all_lessons(db_session: AsyncSession):
    learner = await factories.create_learner(db_session, display_name="Global Student")
    package = await factories.create_package(db_session, learner=learner, title="Global Package")
    await factories.create_lesson(db_session, package=package, sequence_index=1)

    lessons, total = await lesson_service.list_all_lessons(
        db_session,
        search="Global",
        limit=10,
        offset=0,
    )
    assert total == 1
    assert lessons[0].package_title == "Global Package"
