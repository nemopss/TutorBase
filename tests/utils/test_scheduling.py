from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from utils import scheduling

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

@pytest.mark.parametrize(
    "now_str, days, lesson_time, lead_minutes, expected_str",
    [
        # Case 1: Simple case, next week
        (
            "2024-01-01 12:00:00",  # Monday
            [2],  # Wednesday
            "10:00",
            60,
            "2024-01-03 09:00:00",
        ),
        # Case 2: Reminder for today has already passed, should schedule for next week
        (
            "2024-01-03 09:30:00",  # Wednesday 9:30
            [2],  # Wednesday
            "10:00",
            60,
            "2024-01-10 09:00:00", # Next Wednesday
        ),
        # Case 3: Reminder for today is still in the future
        (
            "2024-01-03 08:30:00",  # Wednesday 8:30
            [2],  # Wednesday
            "10:00",
            60,
            "2024-01-03 09:00:00", # Same day
        ),
        # Case 4: Week wrap-around
        (
            "2024-01-05 12:00:00",  # Friday
            [0],  # Monday
            "11:00",
            30,
            "2024-01-08 10:30:00", # Next Monday
        ),
        # Case 5: No valid days
        (
            "2024-01-01 12:00:00",
            [], # No days
            "10:00",
            60,
            None, # Expect None
        ),
    ],
)
def test_compute_next_run_for_recurring(
    now_str, days, lesson_time, lead_minutes, expected_str
):
    """Tests compute_next_run_for_recurring function."""
    now_utc = datetime.fromisoformat(now_str).replace(tzinfo=MOSCOW_TZ).astimezone(timezone.utc)
    
    next_run = scheduling.compute_next_run_for_recurring(
        days=days,
        lesson_time=lesson_time,
        lead_minutes=lead_minutes,
        now_utc=now_utc,
        tz=MOSCOW_TZ,
    )

    if expected_str is None:
        assert next_run is None
    else:
        expected_utc = (
            datetime.fromisoformat(expected_str).replace(tzinfo=MOSCOW_TZ).astimezone(timezone.utc)
        )
        assert next_run is not None
        assert next_run == expected_utc

def test_compute_next_run_for_one_time():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    
    # Reminder in the future
    lesson_dt = datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc)
    next_run = scheduling.compute_next_run_for_one_time(lesson_dt, 60, now)
    assert next_run is not None
    assert next_run.hour == 13

    # Reminder in the past
    lesson_dt_past = datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
    next_run_past = scheduling.compute_next_run_for_one_time(lesson_dt_past, 60, now)
    assert next_run_past is None


@pytest.mark.parametrize(
    "input_str, expected_list",
    [
        ("1,3,5", [1, 3, 5]),
        (" 0, 6 ", [0, 6]),
        ("", []),
        ("1,foo,2", [1, 2]),
        (None, []),
    ],
)
def test_deserialize_days(input_str, expected_list):
    assert scheduling.deserialize_days(input_str) == expected_list


@pytest.mark.parametrize(
    "input_list, expected_str",
    [
        ([0, 1, 2], "Пн, Вт, Ср"),
        ([6, 0], "Пн, Вс"),
        ([], "—"),
    ],
)
def test_humanize_days(input_list, expected_str):
    assert scheduling.humanize_days(input_list) == expected_str
