import pytest
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from services import utils
from database import crud
from database.models import Payment
from tests import factories


def test_normalize_to_utc():
    naive = datetime(2024, 1, 1, 12, 0)
    localized = utils.normalize_to_utc(naive)
    assert localized.tzinfo == timezone.utc

    aware = datetime(2024, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    converted = utils.normalize_to_utc(aware)
    assert converted.tzinfo == timezone.utc


def test_lesson_stats():
    class Lesson:
        def __init__(self, status):
            self.status = status

    total, completed, cancelled = utils.lesson_stats(
        [Lesson("completed"), Lesson("cancelled"), Lesson("scheduled")]
    )
    assert total == 3
    assert completed == 1
    assert cancelled == 1


@pytest.mark.asyncio
async def test_sync_package_metrics(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson1 = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 1, 10, 10, 0, tzinfo=timezone.utc),
    )
    lesson2 = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 1, 12, 15, 0, tzinfo=timezone.utc),
    )
    await db_session.flush()

    updated_package, lessons = await utils.sync_package_metrics(db_session, current_tenant, package.id)
    assert updated_package.start_date == lesson1.scheduled_at
    assert updated_package.end_date == lesson2.scheduled_at
    assert len(lessons) == 2


@pytest.mark.asyncio
async def test_sync_package_metrics_imputes_missing_price_and_recalculates_status(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session)
    learner.lesson_rate = Decimal("2500.00")
    package = await factories.create_package(db_session, learner=learner, status="active")
    package.price = None
    package.payment_status = "unpaid"
    for index in range(6):
        await factories.create_lesson(
            db_session,
            package=package,
            scheduled_at=datetime(2026, 4, 10 + index, 10, 0, tzinfo=timezone.utc),
            sequence_index=index + 1,
        )
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(
        Payment(
            tenant_id=current_tenant.tenant_id,
            learner_id=learner.id,
            package_id=package.id,
            amount=Decimal("15000.00"),
            currency="RUB",
            paid_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()

    updated_package, lessons = await utils.sync_package_metrics(db_session, current_tenant, package.id)

    assert len(lessons) == 6
    assert updated_package.price == Decimal("15000.00")
    assert updated_package.payment_status == "paid"


@pytest.mark.asyncio
async def test_generate_lessons_from_template(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    template = await factories.create_template(
        db_session,
        lesson_count=2,
        default_timezone="Europe/Moscow",
    )
    package = await factories.create_package(db_session, learner=learner, template=template)
    await db_session.flush()

    start_local = datetime(2024, 2, 1, 9, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    await utils.generate_lessons_from_template(db_session, current_tenant, package, template, start_local)
    await db_session.flush()

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    assert len(refreshed.lessons) == template.lesson_count
    for lesson in refreshed.lessons:
        assert lesson.scheduled_at.tzinfo == timezone.utc
