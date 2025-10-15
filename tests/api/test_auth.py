import pytest

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_refresh_token
from api.routes import auth as auth_routes
from config import config
from database import crud


async def _perform_login(client: AsyncClient, *, monkeypatch):
    """Helper to login via DEV_MODE and return response payload."""
    monkeypatch.setattr(config, "DEV_MODE", True)
    monkeypatch.setattr(config, "DEV_INIT_DATA", "dev")
    monkeypatch.setattr(config, "DEV_TELEGRAM_ID", 123456)
    monkeypatch.setattr(config, "DEV_USERNAME", "devuser")
    monkeypatch.setattr(config, "DEV_DISPLAY_NAME", "Dev Tester")
    monkeypatch.setattr(config, "ADMINS", [123456])

    response = await client.post("/api/v1/auth/login", json={"init_data": "dev"})
    return response


@pytest.mark.asyncio
async def test_login_dev_mode_success(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    response = await _perform_login(client, monkeypatch=monkeypatch)

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "admin"
    assert data["user"]["display_name"] == "Dev Tester"
    assert data["access_token"]
    assert data["refresh_token"]

    user = await crud.get_user(db_session, data["user"]["id"])
    assert user is not None
    assert user.role == "admin"
    assert user.username == "devuser"


@pytest.mark.asyncio
async def test_login_invalid_init_data_returns_400(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    response = await client.post("/api/v1/auth/login", json={"init_data": "invalid"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid init data format"


@pytest.mark.asyncio
async def test_login_missing_user_payload_returns_400(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)

    def fake_verify(init_data, bot_token):
        return {"not_user": {}}

    monkeypatch.setattr(auth_routes, "verify_telegram_init_data", fake_verify)

    response = await client.post("/api/v1/auth/login", json={"init_data": "any"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user payload"


@pytest.mark.asyncio
async def test_login_missing_user_id_returns_400(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)

    def fake_verify(init_data, bot_token):
        return {"user": {"username": "tester"}}

    monkeypatch.setattr(auth_routes, "verify_telegram_init_data", fake_verify)

    response = await client.post("/api/v1/auth/login", json={"init_data": "any"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing user id"


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    login_response = await _perform_login(client, monkeypatch=monkeypatch)
    tokens = login_response.json()

    refresh_request = {"refresh_token": tokens["refresh_token"]}
    response = await client.post("/api/v1/auth/refresh", json=refresh_request)
    assert response.status_code == 200

    refreshed = response.json()
    assert refreshed["user"]["id"] == tokens["user"]["id"]
    assert refreshed["access_token"]


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_refresh_user_not_found_returns_401(client: AsyncClient, monkeypatch):
    payload = {"sub": "9999", "role": "viewer", "telegram_id": 999}
    token = create_refresh_token(payload)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"
