from __future__ import annotations

import pytest
from httpx import AsyncClient

from api.routes import health as health_routes


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient, monkeypatch):
    async def fake_ping():
        return True

    monkeypatch.setattr(health_routes.redis_client, "ping", fake_ping)

    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["services"]["database"] == "connected"

    head_response = await client.head("/health")
    assert head_response.status_code == 200
    assert head_response.content == b""


@pytest.mark.asyncio
async def test_readiness_and_liveness(client: AsyncClient, monkeypatch):
    async def fake_ping():
        return True

    monkeypatch.setattr(health_routes.redis_client, "ping", fake_ping)
    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["services"] == {
        "database": "connected",
        "redis": "connected",
    }

    live = await client.get("/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
