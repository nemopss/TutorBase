from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from notifications.domain.entities import NotificationEvent, NotificationTrigger, QuietHours
from notifications.domain.enums import EventType, QuietHoursMode, TriggerType
from notifications.domain.scheduling import apply_quiet_hours, compute_trigger_time

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _msk(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=MOSCOW_TZ)


def test_day_offset_at_time_trigger_uses_event_timezone():
    event = NotificationEvent(
        event_type=EventType.LESSON,
        event_id=617,
        starts_at=_msk(2026, 4, 8, 20),
        timezone="Europe/Moscow",
    )
    trigger = NotificationTrigger(
        trigger_type=TriggerType.DAY_OFFSET_AT_TIME,
        config={"days": -1, "local_time": "10:00"},
    )

    assert compute_trigger_time(trigger, event) == _msk(2026, 4, 7, 10).astimezone(timezone.utc)


def test_relative_offset_trigger_returns_utc():
    event = NotificationEvent(
        event_type=EventType.LESSON,
        event_id=617,
        starts_at=_msk(2026, 4, 8, 20),
        timezone="Europe/Moscow",
    )
    trigger = NotificationTrigger(
        trigger_type=TriggerType.RELATIVE_OFFSET,
        config={"minutes": -60},
    )

    assert compute_trigger_time(trigger, event) == _msk(2026, 4, 8, 19).astimezone(timezone.utc)


def test_absolute_datetime_trigger_accepts_iso_string():
    event = NotificationEvent(event_type=EventType.CUSTOM_DATE, event_id=None)
    trigger = NotificationTrigger(
        trigger_type=TriggerType.ABSOLUTE_DATETIME,
        config={"scheduled_for": "2026-04-10T18:00:00+03:00"},
    )

    assert compute_trigger_time(trigger, event) == datetime(2026, 4, 10, 15, 0, tzinfo=timezone.utc)


def test_quiet_hours_shift_after_start_to_next_end():
    scheduled = _msk(2026, 4, 7, 22, 30)
    quiet_hours = QuietHours(
        start=time(21, 0),
        end=time(9, 0),
        mode=QuietHoursMode.SHIFT,
    )

    shifted, changed = apply_quiet_hours(
        scheduled,
        quiet_hours,
        timezone_name="Europe/Moscow",
    )

    assert changed is True
    assert shifted == _msk(2026, 4, 8, 9, 0).astimezone(timezone.utc)


def test_quiet_hours_shift_before_end_to_same_day_end():
    scheduled = _msk(2026, 4, 7, 8, 30)
    quiet_hours = QuietHours(
        start=time(21, 0),
        end=time(9, 0),
        mode=QuietHoursMode.SHIFT,
    )

    shifted, changed = apply_quiet_hours(
        scheduled,
        quiet_hours,
        timezone_name="Europe/Moscow",
    )

    assert changed is True
    assert shifted == _msk(2026, 4, 7, 9, 0).astimezone(timezone.utc)


def test_quiet_hours_keeps_allowed_time():
    scheduled = _msk(2026, 4, 7, 10, 0)
    quiet_hours = QuietHours(start=time(21, 0), end=time(9, 0))

    shifted, changed = apply_quiet_hours(
        scheduled,
        quiet_hours,
        timezone_name="Europe/Moscow",
    )

    assert changed is False
    assert shifted == scheduled.astimezone(timezone.utc)
