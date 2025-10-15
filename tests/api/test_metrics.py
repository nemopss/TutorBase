from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from tests import factories
from tests.api.utils import make_auth_headers


async def _prepare_data(session: AsyncSession):
    learner = await factories.create_learner(session, display_name="Metric Student")
    package = await factories.create_package(session, learner=learner)
    lesson1 = await factories.create_lesson(
        session,
        package=package,
        scheduled_at=datetime(2024, 4, 10, 9, 0, tzinfo=timezone.utc),
        status="completed",
    )
    lesson2 = await factories.create_lesson(
        session,
        package=package,
        scheduled_at=datetime(2024, 4, 11, 9, 0, tzinfo=timezone.utc),
        status="scheduled",
    )
    rule = await factories.create_reminder_rule(session, package=package, lesson=lesson1, reminder_type="lesson_confirm")
    await factories.create_reminder_instance(
        session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson1,
        status="delivered",
        scheduled_at=datetime(2024, 4, 9, 15, 0, tzinfo=timezone.utc),
    )
    await session.commit()
    return lesson1, lesson2


@pytest.mark.asyncio
async def test_metrics_summary(client: AsyncClient, db_session: AsyncSession):
    await _prepare_data(db_session)
    headers, _ = await make_auth_headers(db_session)

    response = await client.get("/api/v1/metrics/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["lessons"]["completed"] == 1
    assert data["lessons"]["scheduled"] == 1
    assert data["reminders"]["delivered"] == 1


@pytest.mark.asyncio
async def test_lessons_daily_metrics(client: AsyncClient, db_session: AsyncSession):
    lesson1, lesson2 = await _prepare_data(db_session)
    headers, _ = await make_auth_headers(db_session)

    response = await client.get("/api/v1/metrics/lessons/daily", headers=headers)
    assert response.status_code == 200
    dates = {item["date"] for item in response.json()["items"]}
    assert lesson1.scheduled_at.date().isoformat() in dates
    assert lesson2.scheduled_at.date().isoformat() in dates


@pytest.mark.asyncio
async def test_reminders_daily_metrics(client: AsyncClient, db_session: AsyncSession):
    await _prepare_data(db_session)
    headers, _ = await make_auth_headers(db_session)

    response = await client.get("/api/v1/metrics/reminders/daily", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
