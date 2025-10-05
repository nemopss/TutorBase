from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict
from urllib.parse import parse_qsl

import jwt

from config import config

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenVerificationError(Exception):
    """Raised when token verification fails."""


class InitDataVerificationError(Exception):
    """Raised when Telegram initData verification fails."""


def _parse_init_data(init_data: str) -> Dict[str, str]:
    pairs = parse_qsl(init_data, strict_parsing=True)
    return {key: value for key, value in pairs}


def verify_telegram_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    payload = _parse_init_data(init_data)
    hash_value = payload.pop("hash", None)
    if not hash_value:
        raise InitDataVerificationError("Missing hash in init data")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, hash_value):
        raise InitDataVerificationError("Invalid init data signature")

    result: Dict[str, Any] = {}
    for key, value in payload.items():
        if key == "user":
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError as exc:
                raise InitDataVerificationError("Invalid user payload") from exc
        else:
            result[key] = value
    return result


def _create_token(data: Dict[str, Any], token_type: TokenType, expires_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_access_token(data: Dict[str, Any]) -> str:
    return _create_token(data, TokenType.ACCESS, config.JWT_ACCESS_EXPIRES_SECONDS)


def create_refresh_token(data: Dict[str, Any]) -> str:
    return _create_token(data, TokenType.REFRESH, config.JWT_REFRESH_EXPIRES_SECONDS)


def decode_token(token: str, expected_type: TokenType) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenVerificationError("Invalid token") from exc

    token_type = payload.get("type")
    if token_type != expected_type.value:
        raise TokenVerificationError("Unexpected token type")
    return payload

