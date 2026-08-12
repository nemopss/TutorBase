from __future__ import annotations

import pytest

from api.routes import health as health_routes


@pytest.mark.asyncio
async def test_health_check_redis_failure(monkeypatch, client):
    async def fake_ping():
        raise RuntimeError("redis down")

    monkeypatch.setattr(health_routes.redis_client, "ping", fake_ping)
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["services"]["redis"] == "error"


@pytest.mark.asyncio
async def test_health_check_db_failure(monkeypatch, client, app):
    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    async def fake_dependency():
        yield FakeSession()

    app.dependency_overrides[health_routes.get_session] = fake_dependency
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "error" in data["services"]["database"]
    app.dependency_overrides.pop(health_routes.get_session)


@pytest.mark.asyncio
async def test_readiness_fails_when_database_is_unavailable(monkeypatch, client, app):
    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    async def fake_dependency():
        yield FakeSession()

    async def fake_ping():
        return True

    app.dependency_overrides[health_routes.get_session] = fake_dependency
    monkeypatch.setattr(health_routes.redis_client, "ping", fake_ping)
    try:
        response = await client.get("/ready")
    finally:
        app.dependency_overrides.pop(health_routes.get_session)

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["services"]["database"] == "error"
