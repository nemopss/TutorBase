from __future__ import annotations

import pytest

from api import security


def _build_init_data(payload: dict[str, str]) -> str:
    return "&".join(f"{k}={v}" for k, v in payload.items())


def test_parse_init_data_invalid():
    with pytest.raises(security.InitDataVerificationError):
        security._parse_init_data("invalid")


def test_verify_telegram_init_data_missing_hash(monkeypatch):
    monkeypatch.setattr(security, "_parse_init_data", lambda data: {})
    with pytest.raises(security.InitDataVerificationError):
        security.verify_telegram_init_data("a=b", "token")


def test_verify_telegram_init_data_invalid_signature(monkeypatch):
    payload = {"user": "{}", "hash": "bad"}
    monkeypatch.setattr(security, "_parse_init_data", lambda data: payload.copy())
    with pytest.raises(security.InitDataVerificationError):
        security.verify_telegram_init_data("", "token")


def test_verify_telegram_init_data_success(monkeypatch):
    import hmac
    import hashlib

    payload = {"user": "{}"}

    def fake_parse(data):
        parsed = payload.copy()
        secret_key = hmac.new("WebAppData".encode(), "token".encode(), hashlib.sha256).digest()
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
        parsed["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return parsed

    monkeypatch.setattr(security, "_parse_init_data", fake_parse)
    result = security.verify_telegram_init_data("", "token")
    assert result["user"] == {}


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
