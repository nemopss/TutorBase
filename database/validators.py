"""Validation functions for database inputs.

This module contains validation and sanitization functions used across
the application to ensure data integrity and security.

Functions:
    - ensure_positive_int: Validate positive integers
    - ensure_non_empty: Validate non-empty strings with length limits
    - ensure_valid_timezone: Validate timezone identifiers
    - ensure_in_list: Validate enum-like values
    - ensure_positive_int_or_none: Validate optional positive integers
    - escape_like_pattern: Escape SQL LIKE special characters
"""


def ensure_positive_int(value: int, field: str) -> int:
    """Ensure value is a positive integer.
    
    Args:
        value: Value to validate
        field: Field name for error messages
        
    Returns:
        Validated positive integer
        
    Raises:
        ValueError: If value is None or not positive
    """
    if value is None or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value

def ensure_non_empty(value: str, field: str, max_len: int | None = None) -> str:
    """Ensure string is non-empty and within maximum length.
    
    Trims whitespace and validates length constraints.
    
    Args:
        value: String value to validate
        field: Field name for error messages
        max_len: Optional maximum length constraint
        
    Returns:
        Trimmed validated string
        
    Raises:
        ValueError: If value is empty or exceeds max_len
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    trimmed = value.strip()
    if max_len and len(trimmed) > max_len:
        raise ValueError(f"{field} must not exceed {max_len} characters")
    return trimmed

def ensure_valid_timezone(value: str, field: str) -> str:
    """Ensure string is a valid timezone identifier.
    
    Validates against zoneinfo database (e.g., 'Europe/Moscow', 'UTC').
    
    Args:
        value: Timezone string to validate
        field: Field name for error messages
        
    Returns:
        Trimmed validated timezone string
        
    Raises:
        ValueError: If value is empty or not a valid timezone
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if not value or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    try:
        ZoneInfo(value.strip())
    except ZoneInfoNotFoundError:
        raise ValueError(f"{field} must be a valid timezone")
    return value.strip()

def ensure_in_list(value: str, field: str, allowed: list[str]) -> str:
    """Ensure value is one of the allowed options.
    
    Args:
        value: Value to validate
        field: Field name for error messages
        allowed: List of allowed values
        
    Returns:
        Validated value
        
    Raises:
        ValueError: If value is not in allowed list
    """
    if not value or value not in allowed:
        raise ValueError(f"{field} must be one of {allowed}")
    return value

def ensure_positive_int_or_none(value: int | None, field: str) -> int | None:
    """Ensure value is None or a positive integer.
    
    Args:
        value: Value to validate (can be None)
        field: Field name for error messages
        
    Returns:
        None or validated positive integer
        
    Raises:
        ValueError: If value is not None and not positive
    """
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value

def escape_like_pattern(pattern: str) -> str:
    r"""Escape special LIKE characters for SQL safety.
    
    Prevents SQL LIKE injection by escaping special characters.
    Backslash must be escaped first to avoid double-escaping.
    
    Escapes:
        - Backslash (\) → \\
        - Percent (%) → \%
        - Underscore (_) → \_
    
    Args:
        pattern: User-provided search string
        
    Returns:
        Escaped pattern safe for LIKE queries
        
    Examples:
        >>> escape_like_pattern("50% off")
        '50\\% off'
        >>> escape_like_pattern("user_name")
        'user\\_name'
    """
    if not pattern:
        return pattern
    
    # Order matters! Backslash must be escaped first
    return (
        pattern
        .replace('\\', '\\\\')  # \ → \\
        .replace('%', '\\%')    # % → \%
        .replace('_', '\\_')    # _ → \_
    )
