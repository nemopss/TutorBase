from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_list_templates_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/templates")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    await factories.create_template(db_session, name="General English")
    await factories.create_template(db_session, name="Business Course")
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/templates", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    titles = {item["name"] for item in data["items"]}
    assert {"General English", "Business Course"} <= titles


@pytest.mark.asyncio
async def test_get_template_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/templates/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_template(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    payload = {
        "name": "Intensive",
        "description": "Short intensive course",
        "lesson_count": 8,
        "duration_days": 30,
        "default_config": {"weekly_schedule": [{"day": 1, "time": "10:00"}]},
    }

    response = await client.post("/api/v1/templates/create", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Intensive"
    assert data["lesson_count"] == 8

    template = await crud.get_lesson_package_template(db_session, current_tenant, data["id"])
    assert template is not None
    assert template.default_config["weekly_schedule"][0]["day"] == 1


@pytest.mark.asyncio
async def test_update_template(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    template = await factories.create_template(db_session, name="Starter", lesson_count=5)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    payload = {
        "name": "Starter Updated",
        "lesson_count": 6,
        "default_config": {"weekly_schedule": [{"day": 2, "time": "12:00"}]},
    }

    response = await client.patch(f"/api/v1/templates/{template.id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Starter Updated"
    assert data["lesson_count"] == 6

    refreshed = await crud.get_lesson_package_template(db_session, current_tenant, template.id)
    assert refreshed is not None
    assert refreshed.default_config["weekly_schedule"][0]["day"] == 2


@pytest.mark.asyncio
async def test_update_template_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.patch("/api/v1/templates/999", json={"name": "X"}, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_template(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    template = await factories.create_template(db_session, name="To Delete")
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.delete(f"/api/v1/templates/{template.id}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/api/v1/templates/{template.id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_template(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    template = await factories.create_template(db_session, name="Original", lesson_count=3)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.post(f"/api/v1/templates/{template.id}/duplicate", headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"].startswith("Original")
    assert data["lesson_count"] == 3

    templates = await crud.fetch_lesson_package_templates(db_session, current_tenant)
    assert len(templates) == 2
