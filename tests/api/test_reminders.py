from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from database import crud as crud_module
from tests import factories
from tests.api.utils import make_auth_headers


async def _bootstrap_reminder(session: AsyncSession):
    learner = await factories.create_learner(session, display_name="Reminder Learner")
    package = await factories.create_package(session, learner=learner, title="Reminder Package")
    lesson = await factories.create_lesson(session, package=package)
    rule = await factories.create_reminder_rule(
        session,
        package=package,
        lesson=lesson,
        reminder_type="lesson_confirm",
    )
    instance = await factories.create_reminder_instance(
        session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson,
        status="scheduled",
        payload={"student_name": learner.display_name},
    )
    await session.commit()
    return learner, package, lesson, rule, instance


@pytest.mark.asyncio
async def test_list_reminders_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/reminders")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_reminders(client: AsyncClient, db_session: AsyncSession):
    learner, package, _, _, instance = await _bootstrap_reminder(db_session)
    headers, _ = await make_auth_headers(db_session)

    response = await client.get("/api/v1/reminders", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == instance.id
    assert data["items"][0]["payload"]["student_name"] == learner.display_name


@pytest.mark.asyncio
async def test_list_reminders_filters(client: AsyncClient, db_session: AsyncSession):
    learner, package, lesson, rule, _ = await _bootstrap_reminder(db_session)
    await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson,
        status="delivered",
        payload={"student_name": learner.display_name},
    )
    await db_session.commit()

    headers, _ = await make_auth_headers(db_session)
    response = await client.get(
        "/api/v1/reminders",
        params={"status": "delivered"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_list_reminders_for_package(client: AsyncClient, db_session: AsyncSession):
    _, package, _, _, _ = await _bootstrap_reminder(db_session)
    headers, _ = await make_auth_headers(db_session)

    response = await client.get(f"/api/v1/reminders/packages/{package.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_update_reminder(client: AsyncClient, db_session: AsyncSession):
    _, _, _, _, instance = await _bootstrap_reminder(db_session)
    headers, _ = await make_auth_headers(db_session)

    payload = {"status": "delivered", "active": False, "comment": "Sent manually"}
    response = await client.patch(f"/api/v1/reminders/{instance.id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "delivered"
    assert data["active"] is False
    assert data["comment"] == "Sent manually"

    refreshed = await crud.get_reminder_instance(db_session, instance.id)
    assert refreshed is not None
    assert refreshed.status == "delivered"


@pytest.mark.asyncio
async def test_update_reminder_not_found(client: AsyncClient, db_session: AsyncSession):
    headers, _ = await make_auth_headers(db_session)
    response = await client.patch("/api/v1/reminders/999", json={"status": "delivered"}, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_reminder_invalid_payload(client: AsyncClient, db_session: AsyncSession):
    _, _, _, _, instance = await _bootstrap_reminder(db_session)
    headers, _ = await make_auth_headers(db_session)
    response = await client.patch(
        f"/api/v1/reminders/{instance.id}",
        json={"status": ""},
        headers=headers,
    )
    assert response.status_code == 200  # empty status keeps old


@pytest.mark.asyncio
async def test_list_reminders_internal_error(monkeypatch, client: AsyncClient, db_session: AsyncSession):
    headers, _ = await make_auth_headers(db_session)

    async def boom(*args, **kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr(crud, "fetch_reminder_instances_paginated", boom)
    response = await client.get("/api/v1/reminders", headers=headers)
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_list_reminders_for_package_internal_error(monkeypatch, client: AsyncClient, db_session: AsyncSession):
    headers, _ = await make_auth_headers(db_session)

    async def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(crud, "fetch_reminder_instances_for_package", boom)
    response = await client.get("/api/v1/reminders/packages/1", headers=headers)
    assert response.status_code == 500
