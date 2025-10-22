"""Database-specific utility functions.

This module contains database-specific utility functions for SQL operations.
Input validation has been moved to Pydantic schemas at the API boundary.

Functions:
    - escape_like_pattern: Escape SQL LIKE special characters for safe queries

Note:
    Business logic validation (positive integers, non-empty strings, etc.) is now
    handled by Pydantic schemas in api/schemas/. This module only contains
    database-specific utilities that cannot be handled at the API layer.
"""

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
