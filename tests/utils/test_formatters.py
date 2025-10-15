from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from utils import formatters


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "—"),
        ("", "—"),
        ("Hello", "Hello"),
        ("Hello <World>", "Hello &lt;World&gt;"),
    ],
)
def test_escape_html_text(value, expected):
    assert formatters.escape_html_text(value) == expected


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        (None, "—"),
        (datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc), "2024-01-01 15:00:00 MSK"),
        (datetime(2024, 1, 1, 12, 0), "2024-01-01 15:00:00 MSK"),  # Naive datetime
        ("2024-01-01T12:00:00Z", "2024-01-01 15:00:00 MSK"),
        ("2024-01-01T12:00:00+03:00", "2024-01-01 12:00:00 MSK"), # Already MSK
        ("invalid-date-string", "invalid-date-string"),
    ],
)
def test_format_timestamp_msk(raw_value, expected):
    assert formatters.format_timestamp_msk(raw_value) == expected


def test_format_application():
    app_data = {
        "created_at": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        "name": "John Doe",
        "language": "en",
        "level": "B1",
        "preferred_time": "Mon 10:00",
        "contact": "@john",
    }
    output = formatters.format_application(app_data)
    assert "📩 <b>Новая заявка</b>" in output
    assert "<b>Дата:</b> 2024-01-01 15:00:00 MSK" in output
    assert "<b>Имя:</b> John Doe" in output
    assert "<b>Язык:</b> en" in output
    assert "<b>Уровень:</b> B1" in output
    assert "<b>Удобное время:</b> Mon 10:00" in output
    assert "<b>Контакт:</b> @john" in output


def test_format_application_with_none_values():
    app_data = {
        "created_at": None,
        "name": None,
        "language": None,
        "level": None,
        "preferred_time": None,
        "contact": None,
    }
    output = formatters.format_application(app_data)
    assert "📩 <b>Новая заявка</b>" in output
    assert "<b>Дата:</b> —" in output
    assert "<b>Имя:</b> —" in output
    assert "<b>Язык:</b> —" in output
    assert "<b>Уровень:</b> —" in output
    assert "<b>Удобное время:</b> —" in output
    assert "<b>Контакт:</b> —" in output


def test_format_applications_stats():
    stats_data = {
        "total": 5,
        "by_language": {"en": 3, "ru": 2},
        "by_month": {"2024-01": 5},
        "recent": [
            type("obj", (object,), {
                "created_at": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                "name": "App1",
                "language": "en",
                "level": "A1",
            }),
        ],
    }
    output = formatters.format_applications_stats(stats_data)
    assert "Всего заявок: 5" in output
    assert "По языкам:" in output
    assert "- en: 3" in output
    assert "- ru: 2" in output
    assert "По месяцам:" in output
    assert "- 2024-01: 5" in output
    assert "Последние заявки:" in output
    assert "- 2024-01-01 15:00:00 MSK — App1 (en, A1)" in output


def test_format_applications_stats_empty():
    stats_data = {
        "total": 0,
        "by_language": {},
        "by_month": {},
        "recent": [],
    }
    output = formatters.format_applications_stats(stats_data)
    assert "Всего заявок: 0" in output


@pytest.mark.parametrize(
    "display, chat_id, expected",
    [
        ("John Doe", "123", "John Doe|123"),
        (None, "123", "123"),
        ("", "123", "123"),
        ("123", "123", "123"),
        ("John|Doe", "123", "JohnDoe|123"),
        ("", "", ""),
        (None, None, ""),
    ],
)
def test_pack_chat_identifier(display, chat_id, expected):
    assert formatters.pack_chat_identifier(display, chat_id) == expected


@pytest.mark.parametrize(
    "raw, expected_label, expected_chat_id",
    [
        ("John Doe|123", "John Doe", "123"),
        ("123", "123", "123"),
        ("", "", ""),
        (None, "", ""),
        ("  Label |  456  ", "Label", "456"),
    ],
)
def test_split_chat_identifier(raw, expected_label, expected_chat_id):
    label, chat_id = formatters.split_chat_identifier(raw)
    assert label == expected_label
    assert chat_id == expected_chat_id
