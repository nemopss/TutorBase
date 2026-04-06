from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest

from api import security


def _build_init_data(payload: dict[str, str]) -> str:
    return "&".join(f"{k}={v}" for k, v in payload.items())


def _current_auth_date() -> str:
    return str(int(datetime.now(timezone.utc).timestamp()))


def _signed_webapp_init_data(payload: dict[str, str], bot_token: str = "token") -> str:
    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": hash_value})


def _signed_login_widget_data(payload: dict[str, str], bot_token: str = "token") -> dict[str, str]:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return {**payload, "hash": hash_value}


def test_parse_init_data_invalid():
    with pytest.raises(security.InitDataVerificationError):
        security._parse_init_data("invalid")


def test_verify_telegram_init_data_missing_hash(monkeypatch):
    monkeypatch.setattr(security, "_parse_init_data", lambda data: {})
    with pytest.raises(security.InitDataVerificationError):
        security.verify_telegram_init_data("a=b", "token")


def test_verify_telegram_init_data_invalid_signature(monkeypatch):
    payload = {"user": "{}", "auth_date": _current_auth_date(), "hash": "bad"}
    monkeypatch.setattr(security, "_parse_init_data", lambda data: payload.copy())
    with pytest.raises(security.InitDataVerificationError):
        security.verify_telegram_init_data("", "token")


def test_verify_telegram_init_data_missing_auth_date():
    init_data = _signed_webapp_init_data({"user": "{}"})

    with pytest.raises(security.InitDataVerificationError, match="Missing auth_date"):
        security.verify_telegram_init_data(init_data, "token")


def test_verify_telegram_init_data_stale_auth_date():
    init_data = _signed_webapp_init_data({"user": "{}", "auth_date": "1"})

    with pytest.raises(security.InitDataVerificationError, match="outdated"):
        security.verify_telegram_init_data(init_data, "token")


def test_verify_telegram_init_data_success():
    init_data = _signed_webapp_init_data({"user": "{}", "auth_date": _current_auth_date()})

    result = security.verify_telegram_init_data(init_data, "token")
    assert result["user"] == {}
    assert "auth_date" in result


def test_verify_telegram_login_widget_success():
    data = _signed_login_widget_data(
        {
            "id": "123456",
            "first_name": "Test",
            "username": "tester",
            "auth_date": _current_auth_date(),
        }
    )

    result = security.verify_telegram_login_widget(data, "token")

    assert result["id"] == 123456
    assert result["username"] == "tester"


def test_verify_telegram_login_widget_invalid_signature():
    data = _signed_login_widget_data(
        {
            "id": "123456",
            "first_name": "Test",
            "auth_date": _current_auth_date(),
        }
    )
    data["hash"] = "bad"

    with pytest.raises(security.TelegramLoginVerificationError, match="Invalid Telegram login signature"):
        security.verify_telegram_login_widget(data, "token")


@pytest.mark.parametrize(
    "missing_field",
    ["id", "auth_date", "hash"],
)
def test_verify_telegram_login_widget_missing_required_field(missing_field: str):
    data = _signed_login_widget_data(
        {
            "id": "123456",
            "first_name": "Test",
            "auth_date": _current_auth_date(),
        }
    )
    data.pop(missing_field)

    with pytest.raises(security.TelegramLoginVerificationError):
        security.verify_telegram_login_widget(data, "token")


def test_verify_telegram_login_widget_stale_auth_date():
    data = _signed_login_widget_data(
        {
            "id": "123456",
            "first_name": "Test",
            "auth_date": "1",
        }
    )

    with pytest.raises(security.TelegramLoginVerificationError, match="outdated"):
        security.verify_telegram_login_widget(data, "token")


def test_decode_token_wrong_type():
    token = security.create_access_token({"sub": "1"})
    with pytest.raises(security.TokenVerificationError):
        security.decode_token(token, security.TokenType.REFRESH)


def test_create_and_decode_token():
    token = security.create_access_token({"sub": "1", "role": "viewer"})
    payload = security.decode_token(token, security.TokenType.ACCESS)
    assert payload["sub"] == "1"


def test_decode_token_invalid():
    with pytest.raises(security.TokenVerificationError):
        security.decode_token("invalid", security.TokenType.ACCESS)
