"""Security utilities for JWT tokens and Telegram authentication.

This module provides cryptographic functions for:
- JWT token creation and validation (access and refresh tokens)
- Telegram WebApp initData verification
- Secure token comparison and validation

Security features:
    - JWT tokens with configurable expiration
    - HMAC-SHA256 signature verification for Telegram data
    - Timing-safe comparison to prevent timing attacks
    - Token type validation (access vs refresh)
    - Automatic expiration handling

Token types:
    - ACCESS: Short-lived tokens for API authentication (default: 1 hour)
    - REFRESH: Long-lived tokens for obtaining new access tokens (default: 30 days)

Telegram WebApp authentication:
    Uses Telegram's initData validation protocol with HMAC-SHA256.
    Secret key derived from bot token using "WebAppData" constant.

Configuration:
    - JWT_SECRET: Secret key for JWT signing (from config)
    - JWT_ALGORITHM: Algorithm for JWT (default: HS256)
    - JWT_ACCESS_EXPIRES_SECONDS: Access token lifetime
    - JWT_REFRESH_EXPIRES_SECONDS: Refresh token lifetime
"""
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
    """JWT token type enumeration.

    Attributes:
        ACCESS: Short-lived token for API authentication
        REFRESH: Long-lived token for obtaining new access tokens
    """

    ACCESS = "access"
    REFRESH = "refresh"


class TokenVerificationError(Exception):
    """Raised when JWT token verification fails.

    Covers invalid signatures, expired tokens, wrong token type, etc.
    """


class InitDataVerificationError(Exception):
    """Raised when Telegram initData verification fails.

    Covers invalid format, missing hash, signature mismatch, etc.
    """


class TelegramLoginVerificationError(Exception):
    """Raised when Telegram Login Widget verification fails."""


def _parse_init_data(init_data: str) -> Dict[str, str]:
    """Parse Telegram initData query string into dictionary.

    Args:
        init_data: URL-encoded query string from Telegram WebApp

    Returns:
        Dictionary of key-value pairs from initData

    Raises:
        InitDataVerificationError: If format is invalid
    """
    try:
        pairs = parse_qsl(init_data, strict_parsing=True)
    except ValueError as exc:
        raise InitDataVerificationError("Invalid init data format") from exc
    return {key: value for key, value in pairs}


def _validate_auth_date(
    auth_date: Any,
    *,
    max_age_seconds: int | None,
    error_cls: type[Exception],
) -> None:
    """Validate Telegram auth_date freshness."""
    if auth_date in (None, ""):
        raise error_cls("Missing auth_date")

    try:
        auth_timestamp = int(auth_date)
    except (TypeError, ValueError) as exc:
        raise error_cls("Invalid auth_date") from exc

    now_timestamp = int(datetime.now(timezone.utc).timestamp())
    if auth_timestamp > now_timestamp + 60:
        raise error_cls("auth_date is in the future")

    if max_age_seconds is None:
        max_age_seconds = config.TELEGRAM_AUTH_MAX_AGE_SECONDS

    if now_timestamp - auth_timestamp > max_age_seconds:
        raise error_cls("Telegram authentication data is outdated")


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int | None = None,
) -> Dict[str, Any]:
    """Verify Telegram WebApp initData signature and extract payload.

    Implements Telegram's initData validation protocol using HMAC-SHA256.
    Validates that data was sent by Telegram and hasn't been tampered with.

    Security process:
        1. Parse initData query string
        2. Extract hash value
        3. Create data check string from sorted parameters
        4. Derive secret key: HMAC-SHA256("WebAppData", bot_token)
        5. Calculate expected hash: HMAC-SHA256(secret_key, data_check_string)
        6. Compare hashes using timing-safe comparison
        7. Check auth_date freshness
        8. Parse user JSON if present

    Args:
        init_data: URL-encoded initData string from Telegram WebApp
        bot_token: Telegram bot token for signature verification
        max_age_seconds: Maximum accepted auth_date age in seconds

    Returns:
        Dictionary with verified data including parsed user object

    Raises:
        InitDataVerificationError: If signature invalid, hash missing, or format wrong

    Example:
        >>> data = verify_telegram_init_data(init_data, bot_token)
        >>> user_id = data["user"]["id"]
    """
    try:
        payload = _parse_init_data(init_data)
    except InitDataVerificationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise InitDataVerificationError("Failed to parse init data") from exc
    hash_value = payload.pop("hash", None)
    if not hash_value:
        raise InitDataVerificationError("Missing hash in init data")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    
    # For Telegram WebApp, secret key is HMAC of "WebAppData" with bot token
    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, hash_value):
        raise InitDataVerificationError("Invalid init data signature")

    _validate_auth_date(
        payload.get("auth_date"),
        max_age_seconds=max_age_seconds,
        error_cls=InitDataVerificationError,
    )

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


def verify_telegram_login_widget(
    data: Dict[str, Any],
    bot_token: str,
    max_age_seconds: int | None = None,
) -> Dict[str, Any]:
    """Verify Telegram Login Widget data and extract user payload.

    Login Widget data uses a different signature scheme than Mini App initData:
    secret_key = SHA256(bot_token), not HMAC("WebAppData", bot_token).

    Args:
        data: Data returned by Telegram Login Widget.
        bot_token: Telegram bot token for signature verification.
        max_age_seconds: Maximum accepted auth_date age in seconds.

    Returns:
        Verified payload with Telegram user fields.

    Raises:
        TelegramLoginVerificationError: If data is missing, stale, or tampered.
    """
    payload = {key: value for key, value in data.items() if value is not None}
    hash_value = payload.pop("hash", None)
    if not hash_value:
        raise TelegramLoginVerificationError("Missing hash in Telegram login data")

    if not payload.get("id"):
        raise TelegramLoginVerificationError("Missing user id")

    if not payload.get("auth_date"):
        raise TelegramLoginVerificationError("Missing auth_date")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, str(hash_value)):
        raise TelegramLoginVerificationError("Invalid Telegram login signature")

    _validate_auth_date(
        payload.get("auth_date"),
        max_age_seconds=max_age_seconds,
        error_cls=TelegramLoginVerificationError,
    )

    try:
        payload["id"] = int(payload["id"])
    except (TypeError, ValueError) as exc:
        raise TelegramLoginVerificationError("Invalid user id") from exc

    return payload


def _create_token(data: Dict[str, Any], token_type: TokenType, expires_seconds: int) -> str:
    """Create JWT token with specified type and expiration.

    Args:
        data: Payload data to include in token (e.g., user_id, tenant_id)
        token_type: Type of token (ACCESS or REFRESH)
        expires_seconds: Token lifetime in seconds

    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_access_token(data: Dict[str, Any]) -> str:
    """Create short-lived access token for API authentication.

    Args:
        data: Token payload (typically {"sub": user_id, "tenant_id": tenant_id})

    Returns:
        JWT access token string

    Example:
        >>> token = create_access_token({"sub": "123", "tenant_id": 1})
    """
    return _create_token(data, TokenType.ACCESS, config.JWT_ACCESS_EXPIRES_SECONDS)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create long-lived refresh token for obtaining new access tokens.

    Args:
        data: Token payload (typically {"sub": user_id})

    Returns:
        JWT refresh token string

    Example:
        >>> token = create_refresh_token({"sub": "123"})
    """
    return _create_token(data, TokenType.REFRESH, config.JWT_REFRESH_EXPIRES_SECONDS)


def decode_token(token: str, expected_type: TokenType) -> Dict[str, Any]:
    """Decode and validate JWT token with type checking.

    Verifies token signature, expiration, and type. Automatically rejects
    expired tokens and wrong token types.

    Args:
        token: JWT token string to decode
        expected_type: Expected token type (ACCESS or REFRESH)

    Returns:
        Decoded token payload dictionary

    Raises:
        TokenVerificationError: If signature invalid, token expired, or wrong type

    Example:
        >>> payload = decode_token(token, TokenType.ACCESS)
        >>> user_id = payload["sub"]
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenVerificationError("Invalid token") from exc

    token_type = payload.get("type")
    if token_type != expected_type.value:
        raise TokenVerificationError("Unexpected token type")
    return payload
