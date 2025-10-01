from datetime import datetime, timezone
from typing import Dict, Iterable, Any
from zoneinfo import ZoneInfo

from html import escape as _html_escape


def escape_html_text(value: Any, *, default: str = "—") -> str:
    """HTML-экранирование с подстановкой значения по умолчанию."""
    if value is None:
        return default
    text = str(value)
    if text == "":
        return default
    return _html_escape(text)


def format_timestamp_msk(raw_value: datetime | str | None) -> str:
    """Convert ISO timestamp or datetime to Moscow time for display."""
    if not raw_value:
        return "—"
    try:
        if isinstance(raw_value, datetime):
            dt = raw_value
        else:
            normalized = raw_value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S MSK")
    except (ValueError, TypeError):
        return str(raw_value)


def format_application(app: Dict) -> str:
    created_at = escape_html_text(format_timestamp_msk(app.get("created_at")))
    name = escape_html_text(app.get("name"))
    language = escape_html_text(app.get("language"))
    level = escape_html_text(app.get("level"))
    preferred_time = escape_html_text(app.get("preferred_time"))
    contact = escape_html_text(app.get("contact"))
    return (
        f"📩 <b>Новая заявка</b>\n"
        f"<b>Дата:</b> {created_at}\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Язык:</b> {language}\n"
        f"<b>Уровень:</b> {level}\n"
        f"<b>Удобное время:</b> {preferred_time}\n"
        f"<b>Контакт:</b> {contact}\n"
    )


def _format_table_section(title: str, items: Iterable[str]) -> list[str]:
    items = list(items)
    if not items:
        return []
    lines = [title]
    lines.extend(items)
    return lines


def format_applications_stats(stats: Dict) -> str:
    lines: list[str] = [f"Всего заявок: {stats.get('total', 0)}"]

    by_language = stats.get('by_language') or {}
    language_lines = [f"- {escape_html_text(lang)}: {count}" for lang, count in sorted(by_language.items())]
    lines.extend(_format_table_section("По языкам:", language_lines))

    by_month = stats.get('by_month') or {}
    month_lines = [f"- {escape_html_text(month)}: {count}" for month, count in sorted(by_month.items())]
    lines.extend(_format_table_section("По месяцам:", month_lines))

    recent = stats.get('recent') or []
    recent_lines = []
    for app in recent:
        created_at = escape_html_text(format_timestamp_msk(app.created_at))
        recent_lines.append(
            f"- {created_at} — {escape_html_text(app.name)} ({escape_html_text(app.language)}, {escape_html_text(app.level)})"
        )
    lines.extend(_format_table_section("Последние заявки:", recent_lines))

    return "\n".join(lines)


def pack_chat_identifier(display: str, chat_id: str) -> str:
    """Combine contact label with numeric chat id for storage."""
    display = (display or "").strip()
    chat_id = (chat_id or "").strip()
    if not chat_id:
        return display
    if not display or display == chat_id:
        return chat_id
    safe_display = display.replace("|", "").strip()
    return f"{safe_display}|{chat_id}"


def split_chat_identifier(raw: str | None) -> tuple[str, str]:
    """Split stored contact into label and actual chat id."""
    if not raw:
        return "", ""
    if "|" in raw:
        label, actual = raw.split("|", 1)
        return label.strip(), actual.strip()
    value = raw.strip()
    return value, value
