from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Iterable, Sequence

from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def to_utc_iso(dt: datetime) -> str:
    """Return ISO string in UTC for storing in DB."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def compute_next_run_for_recurring(
    days: Sequence[int],
    lesson_time: str,
    lead_minutes: int,
    now_utc: datetime,
    tz: ZoneInfo = MOSCOW_TZ,
) -> datetime | None:
    if not days:
        return None
    lesson_time_obj = parse_time(lesson_time)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_local = now_utc.astimezone(tz)
    for offset in range(0, 14):
        candidate_date = now_local.date() + timedelta(days=offset)
        if (candidate_date.weekday() % 7) not in days:
            continue
        candidate_lesson = datetime.combine(candidate_date, lesson_time_obj, tzinfo=tz)
        reminder_time = candidate_lesson - timedelta(minutes=lead_minutes)
        if reminder_time <= now_local:
            continue
        return reminder_time.astimezone(timezone.utc)
    return None


def compute_next_run_for_one_time(
    lesson_datetime: datetime,
    lead_minutes: int,
    now_utc: datetime,
) -> datetime | None:
    if lesson_datetime.tzinfo is None:
        lesson_datetime = lesson_datetime.replace(tzinfo=timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    reminder_time = lesson_datetime - timedelta(minutes=lead_minutes)
    if reminder_time <= now_utc:
        return None
    return reminder_time


def humanize_days(days: Iterable[int]) -> str:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    mapped = [labels[d % 7] for d in sorted(set(days))]
    return ", ".join(mapped) if mapped else "—"


def serialize_days(days: Iterable[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days)))


def deserialize_days(value: str | None) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for part in value.split(','):
        part = part.strip()
        if part.lstrip('-').isdigit():
            result.append(int(part))
    return result
