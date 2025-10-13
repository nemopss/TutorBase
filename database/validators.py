def ensure_positive_int(value: int, field: str) -> int:
    """Ensures that the provided value is a positive integer."""
    if value is None or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value

def ensure_non_empty(value: str, field: str, max_len: int | None = None) -> str:
    """Ensures that the provided string is non-empty and optionally within a maximum length."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    trimmed = value.strip()
    if max_len and len(trimmed) > max_len:
        raise ValueError(f"{field} must not exceed {max_len} characters")
    return trimmed

def ensure_valid_timezone(value: str, field: str) -> str:
    """Ensures that the provided string is a valid timezone."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if not value or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    try:
        ZoneInfo(value.strip())
    except ZoneInfoNotFoundError:
        raise ValueError(f"{field} must be a valid timezone")
    return value.strip()

def ensure_in_list(value: str, field: str, allowed: list[str]) -> str:
    """Ensures that the provided string is one of the valid options."""
    if not value or value not in allowed:
        raise ValueError(f"{field} must be one of {allowed}")
    return value

def ensure_positive_int_or_none(value: int | None, field: str) -> int | None:
    """Ensures that the provided value is either None or a positive integer."""
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value