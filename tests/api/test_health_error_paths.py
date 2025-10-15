from __future__ import annotations

import pytest

from api.routes import health as health_routes


@pytest.mark.asyncio
async def test_health_check_redis_failure(monkeypatch, client):
    async def fake_ping():
        raise RuntimeError("redis down")

    monkeypatch.setattr(health_routes.redis_client, "ping", fake_ping)
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["services"]["redis"] == "not configured"


@pytest.mark.asyncio
async def test_health_check_db_failure(monkeypatch, client, app):
    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    async def fake_dependency():
        yield FakeSession()

    app.dependency_overrides[health_routes.get_session] = fake_dependency
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "error" in data["services"]["database"]
    app.dependency_overrides.pop(health_routes.get_session)
