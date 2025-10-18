from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from tests import factories
from tests.api.utils import get_auth_headers
from services import package_service


@pytest.fixture(autouse=True)
def disable_reminder_regeneration(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(package_service, "regenerate_reminders_for_package", _noop)


@pytest.mark.asyncio
async def test_list_lessons_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/lessons")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_all_lessons(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session, display_name="Alice Johnson")
    package = await factories.create_package(db_session, learner=learner, title="Speaking Course")
    scheduled = datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)
    await factories.create_lesson(db_session, package=package, scheduled_at=scheduled)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get(
        "/api/v1/lessons",
        params={"search": "Alice"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["package_title"] == "Speaking Course"


@pytest.mark.asyncio
async def test_list_lessons_for_package(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await factories.create_lesson(db_session, package=package)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get(f"/api/v1/lessons/packages/{package.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["package_id"] == package.id


@pytest.mark.asyncio
async def test_list_lessons_for_package_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/lessons/packages/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_lesson_for_package(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "scheduled_at": "2024-07-01T10:00:00Z",
        "duration_minutes": 60,
        "status": "scheduled",
        "teacher_notes": "Introduction",
    }

    response = await client.post(
        f"/api/v1/lessons/packages/{package.id}",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["package_id"] == package.id
    assert body["duration_minutes"] == 60
    assert body["sequence_index"] == 1

    lessons = await crud.fetch_lessons_for_package(db_session, current_tenant, package.id)
    assert len(lessons) == 1


@pytest.mark.asyncio
async def test_create_lesson_for_unknown_package(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    payload = {"scheduled_at": "2024-07-01T10:00:00Z"}
    response = await client.post("/api/v1/lessons/packages/999", json=payload, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_lesson(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.get(f"/api/v1/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == lesson.id


@pytest.mark.asyncio
async def test_get_lesson_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/lessons/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_lesson(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(
        db_session,
        package=package,
        scheduled_at=datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "status": "completed",
        "duration_minutes": 75,
        "teacher_notes": "Great progress",
    }
    response = await client.patch(f"/api/v1/lessons/{lesson.id}", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["duration_minutes"] == 75
    assert body["teacher_notes"] == "Great progress"


@pytest.mark.asyncio
async def test_update_lesson_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.patch("/api/v1/lessons/999", json={}, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_lesson(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.delete(f"/api/v1/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 204

    removed = await crud.get_lesson(db_session, current_tenant, lesson.id)
    assert removed is None


@pytest.mark.asyncio
async def test_delete_lesson_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.delete("/api/v1/lessons/999", headers=headers)
    assert response.status_code == 404
