"""Helpers for keeping secrets out of application logs."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import parse_qsl, urlencode

REDACTED = "[redacted]"

SENSITIVE_PARAM_PARTS = (
    "authorization",
    "cookie",
    "token",
    "refresh",
    "access",
    "password",
    "secret",
    "hash",
    "init_data",
    "initdata",
    "telegram",
    "api_key",
    "apikey",
)


def is_sensitive_log_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in SENSITIVE_PARAM_PARTS)


def _iter_query_items(query_params: object) -> Iterable[tuple[str, object]]:
    if isinstance(query_params, str):
        return parse_qsl(query_params, keep_blank_values=True)

    if hasattr(query_params, "multi_items"):
        return query_params.multi_items()

    if isinstance(query_params, Mapping):
        return query_params.items()

    if hasattr(query_params, "items"):
        return query_params.items()

    return parse_qsl(str(query_params), keep_blank_values=True)


def redact_query_params(query_params: object) -> str:
    """Return a query string with secret-like parameter values redacted."""
    redacted_items = [
        (str(key), REDACTED if is_sensitive_log_key(str(key)) else value)
        for key, value in _iter_query_items(query_params)
    ]
    return urlencode(redacted_items, doseq=True, safe="[]")
