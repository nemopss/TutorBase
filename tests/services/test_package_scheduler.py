from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
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
async def test_regenerate_package_reminders_creates_rules_and_instances(db_session: AsyncSession, current_tenant: CurrentTenant):
    now = datetime.now(timezone.utc)
    learner = await factories.create_learner(
        db_session,
        display_name="Schedule Student",
        chat_id=123456,
    )
    package = await factories.create_package(
        db_session,
        learner=learner,
        status="active",
        total_lessons=2,
        schedule_mode="fixed",
        renewal_enabled=True,
    )
    package.end_date = now + timedelta(days=28)
    lesson1 = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=now + timedelta(days=21),
        sequence_index=1,
    )
    lesson1.has_homework = True
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=now + timedelta(days=28),
        sequence_index=2,
    )
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
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
async def test_regenerate_package_reminders_without_lessons(db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, status="active")
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)
    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    assert not refreshed.reminder_rules


@pytest.mark.asyncio
async def test_regenerate_package_reminders_missing_package_raises(monkeypatch, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await db_session.flush()

    async def fake_get_package(session, current_tenant, package_id):
        return None

    monkeypatch.setattr(crud, "get_lesson_package", fake_get_package)

    with pytest.raises(ValueError):
        await regenerate_package_reminders(db_session, current_tenant, package)


@pytest.mark.asyncio
async def test_flexible_package_does_not_create_payment_or_renewal_reminders(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, chat_id=123456)
    package = await factories.create_package(
        db_session,
        learner=learner,
        status="active",
        total_lessons=10,
    )
    package.end_date = datetime.now(timezone.utc) + timedelta(days=7)
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    reminder_types = {rule.reminder_type for rule in refreshed.reminder_rules}
    assert REMINDER_TYPE_PAYMENT_WEEK not in reminder_types
    assert REMINDER_TYPE_PAYMENT_DAY not in reminder_types
    assert REMINDER_TYPE_PACKAGE_RENEWAL not in reminder_types


@pytest.mark.asyncio
async def test_one_off_lesson_does_not_create_package_reminders(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    learner = await factories.create_learner(db_session, chat_id=123456)
    package = await factories.create_package(
        db_session,
        learner=learner,
        package_type="one_off",
        status="active",
        total_lessons=1,
    )
    package.end_date = datetime.now(timezone.utc) + timedelta(days=7)
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=package.end_date,
    )
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    reminder_types = {rule.reminder_type for rule in refreshed.reminder_rules}
    assert REMINDER_TYPE_PAYMENT_WEEK not in reminder_types
    assert REMINDER_TYPE_PAYMENT_DAY not in reminder_types
    assert REMINDER_TYPE_PACKAGE_RENEWAL not in reminder_types


@pytest.mark.asyncio
async def test_regeneration_preserves_sent_renewal_without_creating_duplicate(
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
):
    now = datetime.now(timezone.utc)
    learner = await factories.create_learner(db_session, chat_id=123456)
    package = await factories.create_package(
        db_session,
        learner=learner,
        status="active",
        total_lessons=1,
        schedule_mode="fixed",
        renewal_enabled=True,
    )
    package.end_date = now + timedelta(days=28)
    await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=package.end_date,
    )
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)
    renewal = next(
        instance
        for instance in package.reminder_instances
        if instance.rule.reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL
    )
    renewal.status = "sent"
    renewal.active = False
    renewal.last_notified_at = now
    await db_session.flush()

    await regenerate_package_reminders(db_session, current_tenant, package)

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    renewals = [
        instance
        for instance in refreshed.reminder_instances
        if instance.rule.reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL
    ]
    assert len(renewals) == 1
    assert renewals[0].status == "sent"
