"""Custom Pydantic validators for business rules.

This module provides reusable custom validators for complex
validation logic that goes beyond simple type/range checks.

Key components:
    - validate_timezone: Validate timezone string
    - validate_status: Validate status enum values
    - validate_future_date: Ensure date is in future
    - validate_date_range: Ensure end_date > start_date

Usage:
    from pydantic import field_validator
    
    class MyModel(BaseModel):
        timezone: str
        
        @field_validator('timezone')
        @classmethod
        def check_timezone(cls, v: str) -> str:
            return validate_timezone(v)
"""
from datetime import datetime, date
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone(value: str) -> str:
    """Validate that string is a valid timezone.
    
    Args:
        value: Timezone string (e.g., 'Europe/Moscow', 'UTC')
        
    Returns:
        Validated timezone string
        
    Raises:
        ValueError: If timezone is invalid
        
    Example:
        >>> validate_timezone('Europe/Moscow')
        'Europe/Moscow'
        >>> validate_timezone('Invalid/Zone')
        ValueError: Invalid timezone: Invalid/Zone
    """
    try:
        ZoneInfo(value)
        return value
    except ZoneInfoNotFoundError:
        raise ValueError(f"Invalid timezone: {value}")


def validate_status(value: str, valid_statuses: list[str]) -> str:
    """Validate that status is in allowed list.
    
    Args:
        value: Status string to validate
        valid_statuses: List of allowed status values
        
    Returns:
        Validated status string
        
    Raises:
        ValueError: If status not in valid list
        
    Example:
        >>> validate_status('active', ['draft', 'active', 'completed'])
        'active'
        >>> validate_status('invalid', ['draft', 'active'])
        ValueError: Status must be one of: draft, active
    """
    if value not in valid_statuses:
        valid_str = ', '.join(valid_statuses)
        raise ValueError(f"Status must be one of: {valid_str}")
    return value


def validate_future_date(value: Optional[datetime]) -> Optional[datetime]:
    """Validate that datetime is in the future.
    
    Args:
        value: Datetime to validate (None is allowed)
        
    Returns:
        Validated datetime
        
    Raises:
        ValueError: If datetime is in the past
        
    Example:
        >>> from datetime import datetime, timedelta
        >>> future = datetime.now() + timedelta(days=1)
        >>> validate_future_date(future)
        datetime(...)
        >>> past = datetime.now() - timedelta(days=1)
        >>> validate_future_date(past)
        ValueError: Date must be in the future
    """
    if value is None:
        return value
    
    if value < datetime.now(value.tzinfo):
        raise ValueError("Date must be in the future")
    
    return value


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Validate that end_date is after start_date.
    
    Args:
        start_date: Start of date range (None is allowed)
        end_date: End of date range (None is allowed)
        
    Returns:
        Tuple of (start_date, end_date)
        
    Raises:
        ValueError: If end_date is before start_date
        
    Example:
        >>> from datetime import datetime
        >>> start = datetime(2024, 1, 1)
        >>> end = datetime(2024, 12, 31)
        >>> validate_date_range(start, end)
        (datetime(2024, 1, 1), datetime(2024, 12, 31))
        >>> validate_date_range(end, start)
        ValueError: End date must be after start date
    """
    if start_date is not None and end_date is not None:
        if end_date <= start_date:
            raise ValueError("End date must be after start date")
    
    return start_date, end_date


def validate_positive_int(value: Optional[int], field_name: str = "value") -> Optional[int]:
    """Validate that integer is positive.
    
    Args:
        value: Integer to validate (None is allowed)
        field_name: Name of field for error message
        
    Returns:
        Validated integer
        
    Raises:
        ValueError: If integer is not positive
        
    Example:
        >>> validate_positive_int(10, "duration")
        10
        >>> validate_positive_int(-5, "duration")
        ValueError: duration must be positive
    """
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    
    return value


__all__ = [
    'validate_timezone',
    'validate_status',
    'validate_future_date',
    'validate_date_range',
    'validate_positive_int',
]
