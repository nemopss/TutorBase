from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from services.package_scheduler import regenerate_package_reminders
from services.reminder_definitions import (
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_PAYMENT_WEEK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
)
from database import crud
from tests import factories


@pytest.mark.asyncio
async def test_regenerate_package_reminders_creates_rules_and_instances(db_session: AsyncSession):
    learner = await factories.create_learner(db_session, display_name="Schedule Student")
    package = await factories.create_package(db_session, learner=learner)
    lesson1 = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
        sequence_index=1,
    )
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 6, 8, 10, 0, tzinfo=timezone.utc),
        sequence_index=2,
    )

    await regenerate_package_reminders(db_session, package)

    refreshed = await crud.get_lesson_package(db_session, package.id)
    rules = refreshed.reminder_rules or []
    instances = refreshed.reminder_instances or []

    types = {rule.reminder_type for rule in rules}
    assert REMINDER_TYPE_LESSON_CONFIRM in types
    assert REMINDER_TYPE_LESSON_DAY_BEFORE in types
    assert REMINDER_TYPE_HOMEWORK in types
    assert REMINDER_TYPE_PACKAGE_RENEWAL in types
    assert REMINDER_TYPE_PAYMENT_WEEK in types or REMINDER_TYPE_PAYMENT_DAY in types

    assert any(instance.lesson_id == lesson1.id for instance in instances)


@pytest.mark.asyncio
async def test_regenerate_package_reminders_without_lessons(db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)

    await regenerate_package_reminders(db_session, package)
    refreshed = await crud.get_lesson_package(db_session, package.id)
    assert not refreshed.reminder_rules


@pytest.mark.asyncio
async def test_regenerate_package_reminders_missing_package_raises(monkeypatch, db_session: AsyncSession):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)

    async def fake_get_package(session, package_id):
        return None

    monkeypatch.setattr(crud, "get_lesson_package", fake_get_package)

    with pytest.raises(ValueError):
        await regenerate_package_reminders(db_session, package)
