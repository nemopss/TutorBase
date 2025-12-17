import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from tests import factories
from tests.api.utils import get_auth_headers
from services import package_service
from services.exceptions import ValidationError


@pytest.mark.asyncio
async def test_packages_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/packages")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_packages_returns_results(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    await factories.create_package(db_session, learner=learner, title="Demo Package", status="active")
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/packages", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Demo Package"


@pytest.mark.asyncio
async def test_create_package_success(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "learner_id": learner.id,
        "title": "Spring Intensive",
        "status": "active",
        "notes": "Focus on speaking",
        "total_lessons": 8,
        "start_date": "2024-03-01",
    }

    response = await client.post("/api/v1/packages", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == payload["title"]
    assert data["notes"] == payload["notes"]
    assert data["total_lessons"] == payload["total_lessons"]

    package = await crud.get_lesson_package(db_session, current_tenant, data["id"])
    assert package is not None
    assert package.status == "active"
    assert package.notes == "Focus on speaking"


@pytest.mark.asyncio
async def test_create_package_requires_start_date_for_template(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    template = await factories.create_template(db_session)
    await db_session.commit()

    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "learner_id": learner.id,
        "title": "Template Package",
        "template_id": template.id,
    }

    response = await client.post("/api/v1/packages", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "start_date required for template"


@pytest.mark.asyncio
async def test_create_package_from_template_generates_lessons(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    template = await factories.create_template(db_session, lesson_count=2)
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "learner_id": learner.id,
        "title": "From Template",
        "template_id": template.id,
        "status": "draft",
        "notes": "Auto generated",
        "start_date": "2024-05-10",
    }

    response = await client.post("/api/v1/packages", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["total_lessons"] == template.lesson_count

    package = await crud.get_lesson_package(db_session, current_tenant, data["id"])
    assert package is not None
    assert len(package.lessons) == template.lesson_count
    assert package.reminder_instances


@pytest.mark.asyncio
async def test_update_package(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, title="Initial", status="draft")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    payload = {
        "title": "Updated",
        "status": "active",
        "notes": "Updated notes",
        "total_lessons": 12,
    }

    response = await client.patch(f"/api/v1/packages/{package.id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated"
    assert data["total_lessons"] == 0

    refreshed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    assert refreshed is not None
    assert refreshed.status == "active"
    assert refreshed.notes == "Updated notes"


@pytest.mark.asyncio
async def test_delete_package(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner, title="To Delete")
    await db_session.commit()
    headers, _ = await get_auth_headers(db_session, current_tenant)

    response = await client.delete(f"/api/v1/packages/{package.id}", headers=headers)
    assert response.status_code == 204

    removed = await crud.get_lesson_package(db_session, current_tenant, package.id)
    assert removed is None


@pytest.mark.asyncio
async def test_get_package_not_found_returns_404(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.get("/api/v1/packages/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_package_endpoint_not_found(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.post("/api/v1/packages/999/regenerate", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_package_invalid_start_date(client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    headers, _ = await get_auth_headers(db_session, current_tenant)
    response = await client.post(
        "/api/v1/packages",
        json={"learner_id": learner.id, "title": "Test", "start_date": "2024-13-01"},
        headers=headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_package_validation_error(monkeypatch, client: AsyncClient, db_session: AsyncSession, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    headers, _ = await get_auth_headers(db_session, current_tenant)

    async def fake_create_package(*args, **kwargs):
        raise ValidationError("invalid")

    monkeypatch.setattr(package_service, "create_package", fake_create_package)

    response = await client.post(
        "/api/v1/packages",
        json={"learner_id": learner.id, "title": "Test"},
        headers=headers,
    )
    assert response.status_code == 400
