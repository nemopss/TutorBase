from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from notifications.domain.entities import NotificationEvent, NotificationTrigger, QuietHours
from notifications.domain.enums import QuietHoursMode, TriggerType


def compute_trigger_time(trigger: NotificationTrigger, event: NotificationEvent) -> datetime:
    tz = _zoneinfo(event.timezone)

    if trigger.trigger_type == TriggerType.ABSOLUTE_DATETIME:
        scheduled_for = trigger.config.get("scheduled_for")
        if scheduled_for is None:
            raise ValueError("absolute_datetime trigger requires scheduled_for")
        return _ensure_aware(_parse_datetime(scheduled_for), tz).astimezone(timezone.utc)

    if trigger.trigger_type == TriggerType.RELATIVE_OFFSET:
        base = _event_datetime(event, trigger.config.get("event_field", "starts_at"))
        minutes = int(trigger.config.get("minutes", 0))
        return (base + timedelta(minutes=minutes)).astimezone(timezone.utc)

    if trigger.trigger_type == TriggerType.AFTER_EVENT_OFFSET:
        base = _event_datetime(event, trigger.config.get("event_field", "ends_at"))
        minutes = int(trigger.config.get("minutes", 0))
        return (base + timedelta(minutes=minutes)).astimezone(timezone.utc)

    if trigger.trigger_type == TriggerType.DAY_OFFSET_AT_TIME:
        base = _event_datetime(event, trigger.config.get("event_field", "starts_at"))
        days = int(trigger.config.get("days", 0))
        local_time = _parse_time(trigger.config.get("local_time"))
        base_local = base.astimezone(tz)
        scheduled_local = (base_local + timedelta(days=days)).replace(
            hour=local_time.hour,
            minute=local_time.minute,
            second=0,
            microsecond=0,
        )
        return scheduled_local.astimezone(timezone.utc)

    raise ValueError(f"Unsupported trigger type: {trigger.trigger_type}")


def apply_quiet_hours(
    scheduled_for: datetime,
    quiet_hours: QuietHours | None,
    *,
    timezone_name: str,
) -> tuple[datetime, bool]:
    if quiet_hours is None or quiet_hours.mode != QuietHoursMode.SHIFT:
        return scheduled_for.astimezone(timezone.utc), False

    tz = _zoneinfo(timezone_name)
    local_dt = _ensure_aware(scheduled_for, timezone.utc).astimezone(tz)
    local_time = local_dt.time().replace(tzinfo=None)
    if not _is_in_quiet_hours(local_time, quiet_hours.start, quiet_hours.end):
        return scheduled_for.astimezone(timezone.utc), False

    # Overnight ranges, for example 21:00-09:00, need different target dates
    # depending on whether the local time is before or after midnight.
    target_date = local_dt.date()
    if quiet_hours.start > quiet_hours.end and local_time >= quiet_hours.start:
        target_date = target_date + timedelta(days=1)

    shifted_local = datetime.combine(target_date, quiet_hours.end, tzinfo=tz)
    return shifted_local.astimezone(timezone.utc), True


def _event_datetime(event: NotificationEvent, event_field: str) -> datetime:
    if event_field in {"starts_at", "lesson.starts_at", "event.starts_at"}:
        value = event.starts_at
    elif event_field in {"ends_at", "lesson.ends_at", "event.ends_at"}:
        value = event.ends_at or event.starts_at
    else:
        raise ValueError(f"Unsupported event_field: {event_field}")
    if value is None:
        raise ValueError(f"Event field {event_field} is not available")
    return _ensure_aware(value, _zoneinfo(event.timezone))


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _parse_time(value: str | time | None) -> time:
    if isinstance(value, time):
        return value
    if not value:
        raise ValueError("local_time is required")
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _ensure_aware(value: datetime, default_tz) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=default_tz)
    return value


def _zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _is_in_quiet_hours(value: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= value < end
    return value >= start or value < end
