"""Centralized timezone utilities."""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

# Default timezone for the application
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def get_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """
    Get ZoneInfo object, fallback to default timezone.
    
    Args:
        tz_name: Timezone name (e.g., "Europe/Moscow"). If None, uses default.
    
    Returns:
        ZoneInfo object for the specified or default timezone.
    """
    if not tz_name:
        return DEFAULT_TZ
    try:
        return ZoneInfo(tz_name)
    except Exception:
        # Fallback to default if invalid timezone
        return DEFAULT_TZ


def to_utc(dt: datetime, tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert datetime to UTC.
    
    Args:
        dt: Datetime to convert
        tz: Source timezone (if dt is naive). If None, uses default.
    
    Returns:
        Datetime in UTC timezone.
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in the specified timezone
        dt = dt.replace(tzinfo=tz or DEFAULT_TZ)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime, tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert datetime to local timezone.
    
    Args:
        dt: Datetime to convert
        tz: Target timezone. If None, uses default.
    
    Returns:
        Datetime in local timezone.
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz or DEFAULT_TZ)


def normalize_to_timezone(dt: Optional[datetime], tz: Optional[ZoneInfo] = None) -> Optional[datetime]:
    """
    Normalize datetime to specified timezone, handling None values.
    
    Args:
        dt: Datetime to normalize (can be None)
        tz: Target timezone. If None, uses default.
    
    Returns:
        Normalized datetime in target timezone, or None if input was None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz or DEFAULT_TZ)


def format_local(
    dt: datetime, 
    tz: Optional[ZoneInfo] = None, 
    fmt: str = '%Y-%m-%d %H:%M'
) -> str:
    """
    Format datetime in local timezone.
    
    Args:
        dt: Datetime to format
        tz: Target timezone. If None, uses default.
        fmt: strftime format string
    
    Returns:
        Formatted datetime string.
    """
    local_dt = to_local(dt, tz)
    return local_dt.strftime(fmt)


def parse_date_string(date_str: str, tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Parse date string (YYYY-MM-DD) to datetime at midnight in specified timezone.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        tz: Timezone for the date. If None, uses default.
    
    Returns:
        Datetime at midnight in specified timezone.
    
    Raises:
        ValueError: If date_str is not in valid format.
    """
    from datetime import datetime as dt_module
    parsed_date = dt_module.strptime(date_str, '%Y-%m-%d').date()
    return dt_module.combine(parsed_date, dt_module.min.time(), tzinfo=tz or DEFAULT_TZ)
