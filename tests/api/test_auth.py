import hashlib
import hmac
from datetime import datetime, timezone

import pytest

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import create_refresh_token
from api.routes import auth as auth_routes
from config import config
from database import crud
from tests import factories


def _current_auth_date() -> str:
    return str(int(datetime.now(timezone.utc).timestamp()))


def _signed_login_widget_data(payload: dict[str, str], bot_token: str = "token") -> dict[str, str]:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return {**payload, "hash": hash_value}


def _browser_login_payload(telegram_id: int, *, bot_token: str = "token") -> dict[str, str]:
    return _signed_login_widget_data(
        {
            "id": str(telegram_id),
            "first_name": "Browser",
            "last_name": "Teacher",
            "username": "browser_teacher",
            "auth_date": _current_auth_date(),
        },
        bot_token=bot_token,
    )


def _configure_browser_auth(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", "token")
    monkeypatch.setattr(config, "BROWSER_REFRESH_COOKIE_SECURE", False)


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


@pytest.mark.asyncio
async def test_browser_telegram_login_teacher_success(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1,
    monkeypatch,
):
    _configure_browser_auth(monkeypatch)
    telegram_id = 777001
    await factories.create_user(
        db_session,
        telegram_id=telegram_id,
        role="teacher",
        tenant_id=tenant_1.id,
        display_name="Existing Teacher",
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/browser/telegram",
        json=_browser_login_payload(telegram_id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert "refresh_token" not in data
    assert data["user"]["role"] == "teacher"
    assert data["user"]["display_name"] == "Browser Teacher"
    assert config.BROWSER_REFRESH_COOKIE_NAME in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_browser_refresh_uses_cookie(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1,
    monkeypatch,
):
    _configure_browser_auth(monkeypatch)
    telegram_id = 777002
    await factories.create_user(
        db_session,
        telegram_id=telegram_id,
        role="teacher",
        tenant_id=tenant_1.id,
    )
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/browser/telegram",
        json=_browser_login_payload(telegram_id),
    )
    assert login_response.status_code == 200

    response = await client.post("/api/v1/auth/browser/refresh")

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert "refresh_token" not in data
    assert config.BROWSER_REFRESH_COOKIE_NAME in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_browser_logout_clears_cookie(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1,
    monkeypatch,
):
    _configure_browser_auth(monkeypatch)
    telegram_id = 777003
    await factories.create_user(
        db_session,
        telegram_id=telegram_id,
        role="teacher",
        tenant_id=tenant_1.id,
    )
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/browser/telegram",
        json=_browser_login_payload(telegram_id),
    )
    assert login_response.status_code == 200

    response = await client.post("/api/v1/auth/browser/logout")

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert config.BROWSER_REFRESH_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie


@pytest.mark.asyncio
async def test_browser_telegram_login_invalid_signature_returns_400(client: AsyncClient, monkeypatch):
    _configure_browser_auth(monkeypatch)
    payload = _browser_login_payload(777004)
    payload["hash"] = "bad"

    response = await client.post("/api/v1/auth/browser/telegram", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Telegram login signature"


@pytest.mark.asyncio
async def test_browser_telegram_login_unregistered_user_returns_403(client: AsyncClient, monkeypatch):
    _configure_browser_auth(monkeypatch)

    response = await client.post(
        "/api/v1/auth/browser/telegram",
        json=_browser_login_payload(777005),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "USER_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_browser_telegram_login_viewer_returns_403(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1,
    monkeypatch,
):
    _configure_browser_auth(monkeypatch)
    telegram_id = 777006
    await factories.create_user(
        db_session,
        telegram_id=telegram_id,
        role="viewer",
        tenant_id=tenant_1.id,
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/browser/telegram",
        json=_browser_login_payload(telegram_id),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "BROWSER_ACCESS_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_browser_refresh_missing_cookie_returns_401(client: AsyncClient, monkeypatch):
    _configure_browser_auth(monkeypatch)

    response = await client.post("/api/v1/auth/browser/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing refresh token"
