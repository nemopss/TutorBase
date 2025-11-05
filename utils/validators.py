"""Validation utilities for TutorBase.

This module contains validation functions for various data types used
throughout the application.
"""
import re
from typing import Optional, Tuple


def validate_chat_identifier(identifier: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate chat identifier format for Telegram.
    
    Validates that a chat identifier is in one of the supported formats:
    - Numeric: "123456789" or "-123456789" (for groups)
    - Username: "@username"
    - Packed: "Name|123456789" or "Name|@username"
    
    Args:
        identifier: Chat identifier string to validate
        
    Returns:
        Tuple of (is_valid, error_message) where:
        - is_valid: True if identifier is valid, False otherwise
        - error_message: None if valid, error description if invalid
        
    Examples:
        >>> validate_chat_identifier("123456789")
        (True, None)
        
        >>> validate_chat_identifier("@username")
        (True, None)
        
        >>> validate_chat_identifier("John Doe|123456789")
        (True, None)
        
        >>> validate_chat_identifier("")
        (False, "Chat identifier is empty")
        
        >>> validate_chat_identifier("invalid")
        (False, "Invalid format: invalid")
    """
    if not identifier:
        return False, "Chat identifier is empty"
    
    identifier = identifier.strip()
    if not identifier:
        return False, "Chat identifier is empty after strip"
    
    # Check packed format (name|id)
    if '|' in identifier:
        parts = identifier.split('|', 1)
        if len(parts) != 2:
            return False, "Invalid packed format (expected: name|id)"
        name, chat_part = parts
        if not name.strip():
            return False, "Name part is empty in packed format"
        identifier = chat_part.strip()
    
    # Check numeric format (including negative for groups)
    if identifier.lstrip('-').isdigit():
        return True, None
    
    # Check username format
    if identifier.startswith('@'):
        username = identifier[1:]
        if not username:
            return False, "Username is empty after @"
        # Telegram username rules: 5-32 characters, alphanumeric + underscore
        if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return False, f"Invalid username format: {username}"
        return True, None
    
    return False, f"Invalid format: {identifier}"


__all__ = ['validate_chat_identifier']
