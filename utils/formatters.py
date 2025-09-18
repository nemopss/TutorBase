from datetime import datetime, timezone
from typing import Dict, Iterable
from zoneinfo import ZoneInfo


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
    created_at = format_timestamp_msk(app.get("created_at"))
    return (
        f"📩 <b>Новая заявка</b>\n"
        f"<b>Дата:</b> {created_at}\n"
        f"<b>Имя:</b> {app['name']}\n"
        f"<b>Язык:</b> {app['language']}\n"
        f"<b>Уровень:</b> {app['level']}\n"
        f"<b>Удобное время:</b> {app['preferred_time']}\n"
        f"<b>Контакт:</b> {app['contact']}\n"
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
    language_lines = [f"- {lang}: {count}" for lang, count in sorted(by_language.items())]
    lines.extend(_format_table_section("По языкам:", language_lines))

    by_month = stats.get('by_month') or {}
    month_lines = [f"- {month}: {count}" for month, count in sorted(by_month.items())]
    lines.extend(_format_table_section("По месяцам:", month_lines))

    recent = stats.get('recent') or []
    recent_lines = []
    for app in recent:
        created_at = format_timestamp_msk(app.created_at)
        recent_lines.append(
            f"- {created_at} — {app.name} ({app.language or '—'}, {app.level or '—'})"
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
