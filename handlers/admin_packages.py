import copy
import heapq
import logging
from datetime import datetime, timezone, timedelta, time
from typing import Optional

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from database import crud
from database.models import LessonPackage, Lesson
from filters.admin import IsAdmin
from services import package_service, lesson_service, template_service
from services.exceptions import NotFoundError
from services.package_scheduler import regenerate_package_reminders
from services.utils import lesson_stats, sync_package_metrics
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk
from utils.scheduling import parse_time


router = Router()

PACKAGES_PER_PAGE = 5
PACKAGE_LEARNERS_PER_PAGE = 6


class PackageCreateStates(StatesGroup):
    selecting_learner = State()
    selecting_template = State()
    title = State()
    notes = State()
    template_start_date = State()


class LessonCreateStates(StatesGroup):
    scheduled_at = State()
    duration = State()


class LessonEditStates(StatesGroup):
    scheduled_at = State()


class LessonStatusStates(StatesGroup):
    value = State()


class LessonNotesStates(StatesGroup):
    value = State()


class LessonDurationStates(StatesGroup):
    value = State()


class PackageEditStates(StatesGroup):
    status = State()
    start_date = State()
    timezone = State()
    notes = State()


class TemplateCreateStates(StatesGroup):
    name = State()
    description = State()
    schedule = State()
    lesson_count = State()
    duration_days = State()
    timezone = State()


class TemplateEditStates(StatesGroup):
    name = State()
    description = State()
    schedule = State()
    lesson_count = State()
    duration_days = State()
    timezone = State()


DAY_NAME_ALIASES = {
    'пн': 0,
    'понедельник': 0,
    'вт': 1,
    'вторник': 1,
    'ср': 2,
    'среда': 2,
    'чт': 3,
    'четверг': 3,
    'пт': 4,
    'пятница': 4,
    'сб': 5,
    'суббота': 5,
    'вс': 6,
    'воскресенье': 6,
}

DAY_INT_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

PACKAGE_STATUS_OPTIONS = [
    ('Черновик', 'draft'),
    ('Активен', 'active'),
    ('Завершён', 'completed'),
    ('Отменён', 'cancelled'),
]

PACKAGE_STATUS_LABELS = {value: label for label, value in PACKAGE_STATUS_OPTIONS}
LESSON_STATUS_LABELS = {
    'scheduled': 'Запланирован',
    'completed': 'Проведён',
    'cancelled': 'Отменён',
}

LESSON_STATUS_OPTIONS = [
    ('🔵 Запланирован', 'scheduled'),
    ('✅ Проведён', 'completed'),
    ('❌ Отменён', 'cancelled'),
]


def _calc_total_pages(total: int, per_page: int) -> int:
    if total <= 0:
        return 1
    return max(1, (total + per_page - 1) // per_page)


async def _safe_edit_message(bot, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if 'message is not modified' in str(exc):
            return
        await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def _discard_user_message(message: types.Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    except Exception as exc:
        logging.debug("Failed to delete user message %s: %s", message.message_id, exc)


async def _send_notice(bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text, disable_notification=True)
    except Exception as exc:
        logging.debug("Failed to send notice to %s: %s", chat_id, exc)


async def _edit_flow_message(bot, data: dict, fallback_message: types.Message, text: str, markup) -> None:
    chat_id = data.get('menu_chat_id', fallback_message.chat.id)
    message_id = data.get('menu_message_id', fallback_message.message_id)
    await _safe_edit_message(bot, chat_id, message_id, text, markup)


def _with_error(prompt: str, error: str) -> str:
    return f"{prompt}\n\n⚠️ {error}"


def _parse_lesson_datetime(raw: str, tz: ZoneInfo) -> datetime:
    candidates = ["%d.%m.%Y %H:%M", "%d.%m %H:%M"]
    for fmt in candidates:
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt == "%d.%m %H:%M":
                parsed = parsed.replace(year=datetime.now(tz).year)
            return parsed.replace(tzinfo=tz)
        except ValueError:
            continue
    raise ValueError


def _format_package_period(package) -> str:
    start = escape_html_text(format_timestamp_msk(package.start_date)) if package.start_date else texts.PACKAGE_PERIOD_UNKNOWN
    end = escape_html_text(format_timestamp_msk(package.end_date)) if package.end_date else texts.PACKAGE_PERIOD_UNKNOWN
    return f"{start} — {end}"


def _iter_weekly_occurrences(
    start_local: datetime,
    schedule: list[dict[str, object]],
    limit: int,
) -> list[datetime]:
    if limit <= 0:
        return []

    heap: list[tuple[datetime, dict[str, object]]] = []
    for item in schedule:
        day = item.get('day')
        time_str = item.get('time')
        if not isinstance(day, int) or not isinstance(time_str, str):
            continue
        try:
            lesson_time = parse_time(time_str)
        except ValueError:
            continue
        days_delta = (day - start_local.weekday()) % 7
        candidate = start_local + timedelta(days=days_delta)
        candidate = candidate.replace(
            hour=lesson_time.hour,
            minute=lesson_time.minute,
            second=0,
            microsecond=0,
        )
        if candidate < start_local:
            candidate += timedelta(days=7)
        heapq.heappush(heap, (candidate, {'day': day, 'time': time_str}))

    occurrences: list[datetime] = []
    while heap and len(occurrences) < limit:
        candidate, item = heapq.heappop(heap)
        occurrences.append(candidate)
        next_candidate = candidate + timedelta(days=7)
        if len(occurrences) < limit:
            heapq.heappush(heap, (next_candidate, item))
    return occurrences


def _compute_auto_end_date(
    start_dt: Optional[datetime],
    tz_name: Optional[str],
    schedule: list[dict[str, object]],
    total_lessons: Optional[int],
) -> Optional[datetime]:
    if not start_dt or not schedule or not total_lessons or total_lessons <= 0:
        return None

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    tz = ZoneInfo(tz_name or 'Europe/Moscow')
    occurrences = _iter_weekly_occurrences(start_dt.astimezone(tz), schedule, total_lessons)
    if not occurrences:
        return None
    return occurrences[-1].astimezone(timezone.utc)


def _package_create_cancel_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data='package_create_cancel')
    builder.adjust(1)
    return builder


def _package_edit_cancel_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data=f'package_edit_cancel:{package_id}:{page}')
    builder.adjust(1)
    return builder


def _package_add_lesson_cancel_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data=f'package_add_lesson_cancel:{package_id}:{page}')
    builder.adjust(1)
    return builder


def _package_lesson_edit_cancel_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data=f'package_lesson_edit_cancel:{package_id}:{page}')
    builder.adjust(1)
    return builder


def _package_edit_timezone_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='🇷🇺 Москва', callback_data=f'package_edit_tz:{package_id}:{page}:Europe/Moscow')
    builder.button(text='🇰🇷 Корея', callback_data=f'package_edit_tz:{package_id}:{page}:Asia/Seoul')
    builder.button(text='✏️ Ввести вручную', callback_data=f'package_edit_tz_custom:{package_id}:{page}')
    builder.button(text='⬅️ Отмена', callback_data=f'package_edit_cancel:{package_id}:{page}')
    builder.adjust(2, 1, 1)
    return builder


def _lesson_status_keyboard(package_id: int, lesson_id: int, idx: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for label, value in LESSON_STATUS_OPTIONS:
        builder.button(
            text=label,
            callback_data=f'package_lesson_status_set:{package_id}:{lesson_id}:{idx}:{page}:{value}',
        )
    builder.button(text='⬅️ Отмена', callback_data=f'package_lesson_edit_cancel:{package_id}:{page}')
    builder.adjust(1)
    return builder


def _package_template_cancel_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data='package_template_cancel')
    builder.adjust(1)
    return builder


def _package_template_edit_cancel_keyboard(template_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data=f'package_template_edit_cancel:{template_id}')
    builder.adjust(1)
    return builder


def _parse_schedule_input(raw: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for part in raw.split(','):
        token = part.strip()
        if not token:
            continue
        pieces = token.split()
        if len(pieces) != 2:
            raise ValueError
        day_token, time_token = pieces
        day_key = DAY_NAME_ALIASES.get(day_token.lower())
        if day_key is None:
            raise ValueError
        lesson_time = parse_time(time_token)
        entries.append({'day': day_key, 'time': lesson_time.strftime('%H:%M')})
    if not entries:
        raise ValueError
    entries.sort(key=lambda item: (item['day'], item['time']))
    return entries


def _humanize_weekly_schedule(schedule: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for item in schedule:
        day = item.get('day')
        time_str = item.get('time')
        if isinstance(day, int) and 0 <= day <= 6 and isinstance(time_str, str):
            lines.append(texts.PACKAGE_TEMPLATE_SCHEDULE_LINE.format(day=DAY_INT_LABELS[day], time=time_str))
    return lines


def _with_current(prompt: str, current: Optional[str]) -> str:
    current_display = escape_html_text(current or '—')
    return f"{prompt}\nТекущее: {current_display}"


def _packages_menu_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='📋 Список пакетов', callback_data='packages_list:1')
    builder.button(text='➕ Создать пакет', callback_data='package_create')
    builder.button(text='📑 Пресеты', callback_data='package_templates')
    builder.button(text='⬅️ Назад', callback_data='back_to_admin_panel')
    builder.adjust(1)
    return builder


def _build_packages_keyboard(packages, page: int, total_pages: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for package in packages:
        learner_name = getattr(package, 'learner_name', None)
        if learner_name is None and getattr(package, 'learner', None):
            learner_name = package.learner.display_name
        label = f"📦 {package.title} — {learner_name or '—'}"
        builder.button(text=label[:64], callback_data=f'package_view:{package.id}:{page}')
    if packages:
        builder.adjust(1)

    if total_pages > 1:
        pagination = []
        if page > 1:
            pagination.append(InlineKeyboardButton(text='⬅️', callback_data=f'packages_list:{page - 1}'))
        pagination.append(InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='noop'))
        if page < total_pages:
            pagination.append(InlineKeyboardButton(text='➡️', callback_data=f'packages_list:{page + 1}'))
        builder.row(*pagination)

    builder.row(InlineKeyboardButton(text='⬅️ Назад', callback_data='packages_manager'))
    return builder


async def _load_learners_page(session: AsyncSession, page: int):
    limit = PACKAGE_LEARNERS_PER_PAGE
    page = max(1, page)
    offset = (page - 1) * limit
    learners, total = await crud.fetch_learners_paginated(session, limit=limit, offset=offset)
    total_pages = _calc_total_pages(total, limit)
    if total_pages > 0 and page > total_pages:
        page = total_pages
        offset = (page - 1) * limit
        learners, total = await crud.fetch_learners_paginated(session, limit=limit, offset=offset)
    return learners, total, total_pages, page


async def _show_learner_picker(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    *,
    page: int,
    template_id: Optional[int] = None,
    template_name: Optional[str] = None,
) -> bool:
    learners, total, total_pages, page = await _load_learners_page(session, page)
    if total == 0 or not learners:
        await query.answer(texts.PACKAGE_CREATE_NO_LEARNERS, show_alert=True)
        return False

    await state.set_state(PackageCreateStates.selecting_learner)
    await state.update_data(
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
        list_page=page,
        template_id=template_id,
        template_name=template_name,
    )

    text = _format_learners_list(learners, total)
    markup = _build_package_learners_keyboard(learners, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()
    return True


def _format_learners_list(learners, total: int) -> str:
    if not learners:
        return texts.PACKAGE_CREATE_NO_LEARNERS
    lines = [texts.PACKAGE_CREATE_SELECT_LEARNER, '']
    for learner in learners:
        lines.append(f"👤 {escape_html_text(learner.display_name)}")
    return '\n'.join(lines)


def _build_package_learners_keyboard(learners, page: int, total_pages: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for learner in learners:
        label = learner.display_name
        if learner.bot_user and learner.bot_user.username:
            label = f"{label} (@{learner.bot_user.username})"
        builder.button(text=f"👤 {label}"[:64], callback_data=f'package_create_select:{learner.id}:{page}')
    if learners:
        builder.adjust(1)

    if total_pages > 1:
        pagination = []
        if page > 1:
            pagination.append(InlineKeyboardButton(text='⬅️', callback_data=f'package_create_page:{page - 1}'))
        pagination.append(InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='noop'))
        if page < total_pages:
            pagination.append(InlineKeyboardButton(text='➡️', callback_data=f'package_create_page:{page + 1}'))
        builder.row(*pagination)

    builder.row(InlineKeyboardButton(text='⬅️ Отмена', callback_data='package_create_cancel'))
    return builder


def _format_packages_list(packages, total: int, page: int) -> str:
    if not packages:
        return texts.PACKAGES_EMPTY
    lines = [texts.PACKAGES_LIST_HEADER.format(total=total), '']
    start_index = (page - 1) * PACKAGES_PER_PAGE + 1
    for idx, package in enumerate(packages, start=start_index):
        learner = getattr(package, 'learner_name', None)
        if learner is None and getattr(package, 'learner', None):
            learner = package.learner.display_name
        if learner is None:
            learner = '—'
        progress = getattr(package, 'progress', None)
        if progress:
            total_lessons = progress.total
            completed_lessons = progress.completed
            cancelled_lessons = progress.cancelled
        else:
            total_lessons, completed_lessons, cancelled_lessons = lesson_stats(package.lessons or [])
        lessons_display = f"{total_lessons}/{completed_lessons}/{cancelled_lessons}"
        status_label = PACKAGE_STATUS_LABELS.get(package.status, package.status or '—')
        lines.append(
            texts.PACKAGES_LIST_ITEM.format(
                index=idx,
                title=escape_html_text(package.title),
                learner=escape_html_text(learner),
                status=escape_html_text(status_label),
                lessons=escape_html_text(lessons_display),
            )
        )
    return '\n'.join(lines)


def _format_package_details(package) -> str:
    period = _format_package_period(package)
    notes = escape_html_text(package.notes or '—')
    progress = getattr(package, 'progress', None)
    if progress:
        total_lessons = progress.total
        completed_lessons = progress.completed
        cancelled_lessons = progress.cancelled
    else:
        total_lessons, completed_lessons, cancelled_lessons = lesson_stats(getattr(package, 'lessons', []) or [])
    lessons_display = f"{total_lessons}/{completed_lessons}/{cancelled_lessons}"
    learner = getattr(package, 'learner_name', None)
    if learner is None and getattr(package, 'learner', None):
        learner = package.learner.display_name
    if learner is None:
        learner = '—'
    status_label = PACKAGE_STATUS_LABELS.get(package.status, package.status or '—')
    return texts.PACKAGE_DETAILS.format(
        title=escape_html_text(package.title),
        learner=escape_html_text(learner),
        status=escape_html_text(status_label),
        lessons=escape_html_text(lessons_display),
        period=period,
        timezone=escape_html_text(package.timezone or 'Europe/Moscow'),
        notes=notes,
    )


def _build_package_details_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='🔄 Обновить напоминания', callback_data=f'package_regenerate:{package_id}:{page}')
    builder.button(text='📚 Уроки', callback_data=f'package_lessons:{package_id}:{page}')
    builder.button(text='➕ Добавить урок', callback_data=f'package_add_lesson:{package_id}:{page}')
    builder.button(text='✏️ Редактировать пакет', callback_data=f'package_edit:{package_id}:{page}')
    builder.button(text='🗑 Удалить пакет', callback_data=f'package_delete_confirm:{package_id}:{page}')
    builder.button(text='⬅️ Назад', callback_data=f'packages_list:{page}')
    builder.adjust(1)
    return builder


def _build_package_status_keyboard(package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for label, value in PACKAGE_STATUS_OPTIONS:
        builder.button(text=label, callback_data=f'package_edit_status:{package_id}:{page}:{value}')
    builder.button(text='⬅️ Отмена', callback_data=f'package_edit_cancel:{package_id}:{page}')
    builder.adjust(2, 2, 1)
    return builder


def _format_lessons_list(lessons, package_title: Optional[str] = None) -> str:
    if not lessons:
        return texts.PACKAGE_LESSONS_EMPTY
    if package_title is None:
        first_package = getattr(lessons[0], 'package', None)
        if first_package is not None:
            package_title = getattr(first_package, 'title', None)
        if package_title is None:
            package_title = getattr(lessons[0], 'package_title', None)
    title = escape_html_text(package_title or '—')
    lines = [texts.PACKAGE_LESSONS_HEADER.format(title=title), '']
    for idx, lesson in enumerate(lessons, start=1):
        scheduled = format_timestamp_msk(lesson.scheduled_at) if lesson.scheduled_at else '—'
        duration = f" ({lesson.duration_minutes} мин)" if lesson.duration_minutes else ''
        status_label = LESSON_STATUS_LABELS.get(lesson.status or 'scheduled', lesson.status or 'scheduled')
        lines.append(
            texts.PACKAGE_LESSON_ITEM.format(
                index=idx,
                scheduled=escape_html_text(scheduled + duration),
                status=escape_html_text(status_label),
            )
        )
    return '\n'.join(lines)


def _build_lessons_keyboard(lessons, package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for idx, lesson in enumerate(lessons, start=1):
        scheduled = format_timestamp_msk(lesson.scheduled_at) if lesson.scheduled_at else '—'
        status = LESSON_STATUS_LABELS.get(lesson.status or 'scheduled', lesson.status or 'scheduled')
        label = f"#{idx} {scheduled} · {status}"
        builder.button(
            text=label[:64],
            callback_data=f'package_lesson_view:{package_id}:{lesson.id}:{idx}:{page}'
        )
    if lessons:
        builder.adjust(1)

    builder.row(InlineKeyboardButton(text='➕ Добавить урок', callback_data=f'package_add_lesson:{package_id}:{page}'))
    builder.row(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'package_view:{package_id}:{page}'))
    return builder


def _format_lesson_detail(lesson, idx: int) -> str:
    scheduled = format_timestamp_msk(lesson.scheduled_at) if lesson.scheduled_at else '—'
    duration = f"{lesson.duration_minutes} мин" if lesson.duration_minutes else '—'
    status = LESSON_STATUS_LABELS.get(lesson.status or 'scheduled', lesson.status or 'scheduled')
    notes = lesson.teacher_notes or '—'
    return (
        f"<b>Урок #{idx}</b>\n"
        f"Дата и время: {escape_html_text(scheduled)}\n"
        f"Длительность: {escape_html_text(duration)}\n"
        f"Статус: {escape_html_text(status)}\n"
        f"Заметка: {escape_html_text(notes)}"
    )


def _build_lesson_detail_keyboard(package_id: int, lesson_id: int, idx: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='🕒 Изменить время', callback_data=f'package_lesson_edit:{package_id}:{lesson_id}:{idx}:{page}')
    builder.button(text='⏱ Длительность', callback_data=f'package_lesson_duration:{package_id}:{lesson_id}:{idx}:{page}')
    builder.button(text='📊 Статус', callback_data=f'package_lesson_status:{package_id}:{lesson_id}:{idx}:{page}')
    builder.button(text='📝 Заметка', callback_data=f'package_lesson_notes:{package_id}:{lesson_id}:{idx}:{page}')
    builder.button(text='🗑 Удалить', callback_data=f'package_lesson_delete_confirm:{package_id}:{lesson_id}:{idx}:{page}')
    builder.button(text='⬅️ К списку', callback_data=f'package_lessons:{package_id}:{page}')
    builder.adjust(1)
    return builder


async def _show_lesson_detail(bot, data: dict, fallback_message, package, lesson, idx: int, page: int) -> None:
    text = _format_lesson_detail(lesson, idx)
    markup = _build_lesson_detail_keyboard(package.id, lesson.id, idx, page).as_markup()
    await _edit_flow_message(bot, data, fallback_message, text, markup)


def _format_templates_list(templates, total: int) -> str:
    if not templates:
        return texts.PACKAGE_TEMPLATES_EMPTY
    lines = [texts.PACKAGE_TEMPLATES_LIST_HEADER.format(total=total), '']
    for idx, template in enumerate(templates, start=1):
        lesson_count = template.lesson_count or '—'
        duration_days = template.duration_days or '—'
        lines.append(
            texts.PACKAGE_TEMPLATE_LIST_ITEM.format(
                index=idx,
                name=escape_html_text(template.name),
                lessons=escape_html_text(lesson_count),
                duration=escape_html_text(duration_days),
            )
        )
    return '\n'.join(lines)


def _build_templates_keyboard(templates) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for template in templates:
        builder.button(
            text=f"📑 {template.name}"[:64],
            callback_data=f'package_template_view:{template.id}'
        )
    if templates:
        builder.adjust(1)
    builder.row(InlineKeyboardButton(text='➕ Создать пресет', callback_data='package_template_create'))
    builder.row(InlineKeyboardButton(text='⬅️ Назад', callback_data='packages_manager'))
    return builder


def _build_template_select_keyboard(templates) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for template in templates:
        builder.button(
            text=f"📑 {template.name}"[:64],
            callback_data=f'package_create_template:{template.id}'
        )
    builder.button(text='🧾 Без пресета', callback_data='package_create_template:none')
    builder.button(text='⬅️ Отмена', callback_data='package_create_cancel')
    builder.adjust(1)
    return builder


def _format_template_details(template) -> str:
    description = escape_html_text(template.description or '—')
    lesson_count = escape_html_text(template.lesson_count or '—')
    duration = escape_html_text(template.duration_days or '—')
    timezone_name = escape_html_text(getattr(template, 'default_timezone', None) or getattr(template, 'timezone', 'Europe/Moscow'))
    base = texts.PACKAGE_TEMPLATE_DETAILS.format(
        name=escape_html_text(template.name),
        lesson_count=lesson_count,
        duration_days=duration,
        timezone=timezone_name,
        description=description,
    )
    schedule_lines = _humanize_weekly_schedule((template.default_config or {}).get('weekly_schedule', []))
    if schedule_lines:
        base += '\n\n' + '\n'.join(schedule_lines)
    return base


def _build_template_details_keyboard(template_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='📦 Создать пакет', callback_data=f'package_template_create_package:{template_id}')
    builder.button(text='✏️ Редактировать', callback_data=f'package_template_edit:{template_id}')
    builder.button(text='📄 Копировать', callback_data=f'package_template_copy:{template_id}')
    builder.button(text='🗑 Удалить', callback_data=f'package_template_delete_confirm:{template_id}')
    builder.button(text='⬅️ Назад', callback_data='package_templates')
    builder.adjust(1, 2, 1, 1)
    return builder


@router.callback_query(F.data == 'packages_manager', IsAdmin())
async def cb_packages_manager(query: CallbackQuery, state: FSMContext):
    await state.clear()
    markup = _packages_menu_keyboard().as_markup()
    await query.message.edit_text(texts.ADMIN_PACKAGES_MENU, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data == 'package_templates', IsAdmin())
async def cb_package_templates(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    await state.clear()
    templates = await template_service.list_templates(session)
    text = _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await query.message.edit_text(texts.PACKAGE_TEMPLATES_MENU + '\n\n' + text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_template_view:'), IsAdmin())
async def cb_package_template_view(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    text = _format_template_details(template)
    markup = _build_template_details_keyboard(template_id).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data == 'package_template_create', IsAdmin())
async def cb_package_template_create(query: CallbackQuery, state: FSMContext):
    await state.set_state(TemplateCreateStates.name)
    await state.update_data(
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )
    markup = _package_template_cancel_keyboard().as_markup()
    await query.message.edit_text(texts.PACKAGE_TEMPLATE_PROMPT_NAME, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_template_delete_confirm:'), IsAdmin())
async def cb_package_template_delete_confirm(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text='✅ Да, удалить', callback_data=f'package_template_delete:{template_id}')
    builder.button(text='⬅️ Назад', callback_data=f'package_template_view:{template_id}')
    builder.adjust(1)
    await query.message.edit_text(
        texts.PACKAGE_TEMPLATE_DELETE_CONFIRM.format(name=escape_html_text(template.name)),
        reply_markup=builder.as_markup(),
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_template_delete:'), IsAdmin())
async def cb_package_template_delete(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    try:
        await template_service.delete_template(session, template_id)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to delete template %s: %s", template_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    templates = await template_service.list_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_TEMPLATE_DELETED)


@router.callback_query(F.data == 'package_template_cancel', IsAdmin())
async def cb_package_template_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)
    await state.clear()
    templates = await template_service.list_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, text, markup)
    await query.answer(texts.PACKAGE_TEMPLATE_CANCELLED)


@router.callback_query(F.data.startswith('package_template_create_package:'), IsAdmin())
async def cb_package_template_create_package(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    await _show_learner_picker(
        query,
        state,
        session,
        page=1,
        template_id=template.id,
        template_name=template.name,
    )


@router.callback_query(F.data.startswith('package_template_edit_cancel:'), IsAdmin())
async def cb_package_template_edit_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        template_id = None

    await state.clear()

    if template_id:
        try:
            template = await template_service.get_template(session, template_id)
        except NotFoundError:
            template = None
        if template:
            text = _format_template_details(template)
            markup = _build_template_details_keyboard(template_id).as_markup()
            await query.message.edit_text(text, reply_markup=markup)
            await query.answer(texts.PACKAGE_TEMPLATE_CANCELLED)
            return

    templates = await template_service.list_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_TEMPLATE_CANCELLED)


@router.callback_query(F.data.startswith('package_template_copy:'), IsAdmin())
async def cb_package_template_copy(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    base_name = template.name
    new_name = f"{base_name} (копия)"
    existing_names = {t.name for t in await template_service.list_templates(session)}
    counter = 1
    while new_name in existing_names:
        counter += 1
        new_name = f"{base_name} (копия {counter})"

    try:
        new_template = await template_service.duplicate_template(
            session,
            template_id,
            name=new_name,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to copy template %s: %s", template_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    templates = await template_service.list_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_TEMPLATE_CREATED_FROM.format(
        name=escape_html_text(new_template.name),
        source=escape_html_text(template.name),
    ))


@router.callback_query(F.data.startswith('package_template_edit:'), IsAdmin())
async def cb_package_template_edit(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    await state.set_state(TemplateEditStates.name)
    await state.update_data(
        template_id=template_id,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
        original_config=copy.deepcopy(template.default_config or {}),
        original_name=template.name,
        original_description=template.description,
        original_lesson_count=template.lesson_count,
        original_duration_days=template.duration_days,
        original_timezone=getattr(template, 'default_timezone', None) or template.timezone,
    )

    prompt = texts.PACKAGE_TEMPLATE_PROMPT_NAME_EDIT.format(current=escape_html_text(template.name))
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()
    await query.message.edit_text(prompt, reply_markup=markup)
    await query.answer()


@router.message(TemplateEditStates.name, F.text, IsAdmin())
async def state_template_edit_name(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    await state.update_data(edit_name=None if text in {'', '-'} else text)
    data = await state.get_data()
    await _discard_user_message(message)
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()
    prompt = _with_current(
        texts.PACKAGE_TEMPLATE_PROMPT_DESCRIPTION_EDIT,
        data.get('original_description'),
    )
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        prompt,
        markup,
    )
    await state.set_state(TemplateEditStates.description)


@router.message(TemplateEditStates.description, F.text, IsAdmin())
async def state_template_edit_description(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    await state.update_data(edit_description=None if text in {'', '-'} else text)
    data = await state.get_data()
    await _discard_user_message(message)
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()
    current_schedule = data.get('original_config', {}).get('weekly_schedule', [])
    schedule_lines = '\n'.join(_humanize_weekly_schedule(current_schedule)) or '—'
    prompt = _with_current(texts.PACKAGE_TEMPLATE_PROMPT_SCHEDULE_EDIT, schedule_lines)
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        prompt,
        markup,
    )
    await state.set_state(TemplateEditStates.schedule)

@router.callback_query(F.data == 'package_create', IsAdmin())
async def cb_package_create(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    await _show_learner_picker(query, state, session, page=1, template_id=None, template_name=None)


@router.callback_query(PackageCreateStates.selecting_learner, F.data.startswith('package_create_page:'), IsAdmin())
async def cb_package_create_page(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, page_str = query.data.split(':')
        page = int(page_str)
    except (ValueError, IndexError):
        page = 1

    learners, total, total_pages, page = await _load_learners_page(session, page)
    await state.update_data(list_page=page)

    text = _format_learners_list(learners, total)
    markup = _build_package_learners_keyboard(learners, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(PackageCreateStates.selecting_learner, F.data.startswith('package_create_select:'), IsAdmin())
async def cb_package_create_select(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, learner_id_str, page_str = query.data.split(':')
        learner_id = int(learner_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    learner = await crud.get_learner(session, learner_id)
    if not learner:
        await query.answer(texts.LEARNER_NOT_FOUND, show_alert=True)
        return

    data = await state.get_data()
    preselected_template_id = data.get('template_id')
    preselected_template_name = data.get('template_name')

    await state.update_data(
        learner_id=learner_id,
        learner_name=learner.display_name,
        list_page=page,
    )

    if preselected_template_id:
        await state.set_state(PackageCreateStates.title)
        prompt = texts.PACKAGE_PROMPT_TITLE_TEMPLATE.format(
            default=escape_html_text(preselected_template_name or '—')
        )
        markup = _package_create_cancel_keyboard().as_markup()
        await query.message.edit_text(prompt, reply_markup=markup)
    else:
        templates = await template_service.list_templates(session)
        if templates:
            await state.set_state(PackageCreateStates.selecting_template)
            text = texts.PACKAGE_TEMPLATE_SELECT_PROMPT
            markup = _build_template_select_keyboard(templates).as_markup()
            await query.message.edit_text(text, reply_markup=markup)
        else:
            await state.set_state(PackageCreateStates.title)
            markup = _package_create_cancel_keyboard().as_markup()
            await query.message.edit_text(texts.PACKAGE_PROMPT_TITLE, reply_markup=markup)
    await query.answer()


@router.callback_query(PackageCreateStates.selecting_template, F.data.startswith('package_create_template:'), IsAdmin())
async def cb_package_create_template_choice(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
    except (ValueError, IndexError):
        await query.answer()
        return

    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)

    if template_id_str == 'none':
        await state.update_data(template_id=None, template_name=None)
        await state.set_state(PackageCreateStates.title)
        markup = _package_create_cancel_keyboard().as_markup()
        await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.PACKAGE_PROMPT_TITLE, markup)
        await query.answer()
        return

    try:
        template_id = int(template_id_str)
    except ValueError:
        await query.answer()
        return

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    await state.update_data(template_id=template_id, template_name=template.name)
    await state.set_state(PackageCreateStates.title)

    prompt = texts.PACKAGE_PROMPT_TITLE_TEMPLATE.format(default=escape_html_text(template.name))
    markup = _package_create_cancel_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, prompt, markup)
    await query.answer()


@router.callback_query(F.data == 'package_create_cancel', IsAdmin())
async def cb_package_create_cancel(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)
    await state.clear()
    markup = _packages_menu_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.ADMIN_PACKAGES_MENU, markup)
    await query.answer(texts.PACKAGE_CREATE_CANCELLED)


@router.callback_query(F.data.startswith('package_edit_cancel:'), IsAdmin())
async def cb_package_edit_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        package_id = None
        page = 1

    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)
    await state.clear()

    if package_id:
        try:
            package = await package_service.get_package(session, package_id)
        except NotFoundError:
            package = None
        if package:
            detail_text = _format_package_details(package)
            detail_markup = _build_package_details_keyboard(package_id, page).as_markup()
            await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
            await query.answer(texts.PACKAGE_EDIT_CANCELLED)
            return

    markup = _packages_menu_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.ADMIN_PACKAGES_MENU, markup)
    await query.answer(texts.PACKAGE_EDIT_CANCELLED)


@router.callback_query(PackageEditStates.status, F.data.startswith('package_edit_status:'), IsAdmin())
async def cb_package_edit_status(query: CallbackQuery, state: FSMContext):
    try:
        _, package_id_str, page_str, value = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    await state.update_data(status=value)
    data = await state.get_data()
    markup = _package_edit_cancel_keyboard(package_id, page).as_markup()
    await _safe_edit_message(
        query.bot,
        data.get('menu_chat_id', query.message.chat.id),
        data.get('menu_message_id', query.message.message_id),
        texts.PACKAGE_EDIT_PROMPT_START,
        markup,
    )
    await state.set_state(PackageEditStates.start_date)
    await query.answer()


@router.message(PackageCreateStates.title, F.text, IsAdmin())
async def state_package_title(message: types.Message, state: FSMContext):
    title = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    template_name = data.get('template_name')
    await _discard_user_message(message)

    prompt = (
        texts.PACKAGE_PROMPT_TITLE_TEMPLATE.format(default=escape_html_text(template_name))
        if template_id
        else texts.PACKAGE_PROMPT_TITLE
    )

    if template_id and title in {'', '-'}:
        title = template_name

    if not title:
        markup = _package_create_cancel_keyboard().as_markup()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(prompt, texts.PACKAGE_TITLE_REQUIRED),
            markup,
        )
        return

    await state.update_data(title=title)
    markup = _package_create_cancel_keyboard().as_markup()
    await _edit_flow_message(message.bot, data, message, texts.PACKAGE_PROMPT_NOTES, markup)
    await state.set_state(PackageCreateStates.notes)


@router.message(PackageCreateStates.notes, F.text, IsAdmin())
async def state_package_notes(message: types.Message, state: FSMContext, session: AsyncSession):
    note_text = (message.text or '').strip()
    notes = None if note_text in {'', '-'} else note_text

    data = await state.get_data()
    learner_id = data.get('learner_id')
    title = data.get('title')
    list_page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    template_id = data.get('template_id')

    await _discard_user_message(message)

    if not learner_id or not title:
        await state.clear()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            texts.DATABASE_ERROR,
            _package_create_cancel_keyboard().as_markup(),
        )
        return

    if template_id:
        await state.update_data(notes=notes)
        markup = _package_create_cancel_keyboard().as_markup()
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            texts.PACKAGE_TEMPLATE_PROMPT_START_DATE,
            markup,
        )
        await state.set_state(PackageCreateStates.template_start_date)
        return

    learner = await crud.get_learner(session, learner_id)
    if not learner:
        await state.clear()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            texts.LEARNER_NOT_FOUND,
            _package_create_cancel_keyboard().as_markup(),
        )
        return

    try:
        package_dto = await package_service.create_package(
            session,
            learner_id=learner.id,
            title=title,
            notes=notes,
        )
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            texts.LEARNER_NOT_FOUND,
            _package_create_cancel_keyboard().as_markup(),
        )
        await state.clear()
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create package: %s", exc, exc_info=True)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            texts.DATABASE_ERROR,
            _package_create_cancel_keyboard().as_markup(),
        )
        await state.clear()
        return

    package = await package_service.get_package(session, package_dto.id)
    detail_text = f"{texts.PACKAGE_CREATED_NOTICE}\n\n{_format_package_details(package)}"
    detail_markup = _build_package_details_keyboard(package.id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await state.clear()


@router.message(PackageCreateStates.template_start_date, F.text, IsAdmin())
async def state_package_template_start_date(message: types.Message, state: FSMContext, session: AsyncSession):
    raw = (message.text or '').strip()
    try:
        start_date_value = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        await _discard_user_message(message)
        data = await state.get_data()
        markup = _package_create_cancel_keyboard().as_markup()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_START_DATE, texts.PACKAGE_TEMPLATE_INVALID_DATE),
            markup,
        )
        return

    data = await state.get_data()
    learner_id = data.get('learner_id')
    template_id = data.get('template_id')
    title = data.get('title')
    notes = data.get('notes')
    list_page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    await _discard_user_message(message)

    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await state.clear()
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            texts.PACKAGE_NOT_FOUND,
            _package_create_cancel_keyboard().as_markup(),
        )
        await state.clear()
        return

    timezone_name = 'Europe/Moscow'
    tz = ZoneInfo(timezone_name)
    start_local = datetime.combine(start_date_value, time.min, tz)

    try:
        package_dto = await package_service.create_package_from_template(
            session,
            learner_id=learner_id,
            template_id=template_id,
            title=title,
            notes=notes,
            start_local=start_local,
        )
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            texts.PACKAGE_NOT_FOUND,
            _package_create_cancel_keyboard().as_markup(),
        )
        await state.clear()
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create package from template %s: %s", template_id, exc, exc_info=True)
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            texts.DATABASE_ERROR,
            _package_create_cancel_keyboard().as_markup(),
        )
        await state.clear()
        return

    package = await package_service.get_package(session, package_dto.id)
    detail_text = f"{texts.PACKAGE_CREATED_NOTICE}\n\n{_format_package_details(package)}"
    detail_markup = _build_package_details_keyboard(package.id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await state.clear()


@router.message(TemplateCreateStates.name, F.text, IsAdmin())
async def state_template_name(message: types.Message, state: FSMContext):
    name = (message.text or '').strip()
    data = await state.get_data()
    markup = _package_template_cancel_keyboard().as_markup()
    await _discard_user_message(message)

    if not name:
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_NAME, texts.PACKAGE_TITLE_REQUIRED),
            markup,
        )
        await state.set_state(TemplateCreateStates.name)
        return

    await state.update_data(name=name)
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_DESCRIPTION, markup)
    await state.set_state(TemplateCreateStates.description)


@router.message(TemplateCreateStates.description, F.text, IsAdmin())
async def state_template_description(message: types.Message, state: FSMContext):
    description = (message.text or '').strip()
    await state.update_data(description=None if description in {'', '-'} else description)
    data = await state.get_data()
    await _discard_user_message(message)
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_SCHEDULE, markup)
    await state.set_state(TemplateCreateStates.schedule)


@router.message(TemplateCreateStates.schedule, F.text, IsAdmin())
async def state_template_schedule(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    markup = _package_template_cancel_keyboard().as_markup()

    try:
        schedule = _parse_schedule_input(raw)
    except ValueError:
        await _discard_user_message(message)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_SCHEDULE, texts.PACKAGE_TEMPLATE_INVALID_SCHEDULE),
            markup,
        )
        await state.set_state(TemplateCreateStates.schedule)
        return

    await _discard_user_message(message)
    await state.update_data(schedule=schedule)
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT, markup)
    await state.set_state(TemplateCreateStates.lesson_count)


@router.message(TemplateEditStates.schedule, F.text, IsAdmin())
async def state_template_edit_schedule(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()

    if raw in {'', '-'}:
        schedule = None
    else:
        try:
            schedule = _parse_schedule_input(raw)
        except ValueError:
            await _discard_user_message(message)
            current_schedule = data.get('original_config', {}).get('weekly_schedule', [])
            schedule_lines = '\n'.join(_humanize_weekly_schedule(current_schedule)) or '—'
            prompt = _with_error(
                _with_current(texts.PACKAGE_TEMPLATE_PROMPT_SCHEDULE_EDIT, schedule_lines),
                texts.PACKAGE_TEMPLATE_INVALID_SCHEDULE,
            )
            await _edit_flow_message(message.bot, data, message, prompt, markup)
            await state.set_state(TemplateEditStates.schedule)
            return

    await state.update_data(edit_schedule=schedule)
    data = await state.get_data()
    await _discard_user_message(message)
    current_lessons = data.get('original_lesson_count')
    prompt = texts.PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT_EDIT.format(
        current=escape_html_text(current_lessons or '—')
    )
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        prompt,
        markup,
    )
    await state.set_state(TemplateEditStates.lesson_count)


def _parse_optional_positive_int(raw: str) -> Optional[int]:
    raw = raw.strip()
    if raw in {'', '-'}:
        return None
    if not raw.isdigit():
        raise ValueError
    value = int(raw)
    if value <= 0:
        raise ValueError
    return value


@router.message(TemplateCreateStates.lesson_count, F.text, IsAdmin())
async def state_template_lessons(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    markup = _package_template_cancel_keyboard().as_markup()
    try:
        lesson_count = _parse_optional_positive_int(raw)
    except ValueError:
        await _discard_user_message(message)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT, texts.PACKAGE_TEMPLATE_INVALID_NUMBER),
            markup,
        )
        await state.set_state(TemplateCreateStates.lesson_count)
        return
    await state.update_data(lesson_count=lesson_count)
    data = await state.get_data()
    await _discard_user_message(message)
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_DURATION, markup)
    await state.set_state(TemplateCreateStates.duration_days)


@router.message(TemplateCreateStates.duration_days, F.text, IsAdmin())
async def state_template_duration(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    markup = _package_template_cancel_keyboard().as_markup()
    try:
        duration_days = _parse_optional_positive_int(raw)
    except ValueError:
        await _discard_user_message(message)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_DURATION, texts.PACKAGE_TEMPLATE_INVALID_NUMBER),
            markup,
        )
        await state.set_state(TemplateCreateStates.duration_days)
        return
    await state.update_data(duration_days=duration_days)
    data = await state.get_data()
    await _discard_user_message(message)
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE, markup)
    await state.set_state(TemplateCreateStates.timezone)


@router.message(TemplateCreateStates.timezone, F.text, IsAdmin())
async def state_template_timezone(message: types.Message, state: FSMContext, session: AsyncSession):
    tz_name = (message.text or '').strip() or 'Europe/Moscow'
    data = await state.get_data()
    prompt_markup = _package_template_cancel_keyboard().as_markup()
    try:
        ZoneInfo(tz_name)
    except Exception:
        await _discard_user_message(message)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE, texts.PACKAGE_EDIT_INVALID_TIMEZONE),
            prompt_markup,
        )
        await state.set_state(TemplateCreateStates.timezone)
        return

    await _discard_user_message(message)
    name = data.get('name')
    description = data.get('description')
    lesson_count = data.get('lesson_count')
    duration_days = data.get('duration_days')
    schedule = data.get('schedule') or []
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    try:
        template_dto = await template_service.create_template(
            session,
            name=name,
            description=description,
            lesson_count=lesson_count,
            duration_days=duration_days,
            default_timezone=tz_name,
            default_config={'weekly_schedule': schedule},
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create template: %s", exc, exc_info=True)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE, texts.DATABASE_ERROR),
            prompt_markup,
        )
        await state.set_state(TemplateCreateStates.timezone)
        return

    templates = await template_service.list_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await _send_notice(
        message.bot,
        menu_chat_id,
        texts.PACKAGE_TEMPLATE_CREATED.format(name=escape_html_text(template_dto.name)),
    )
    await state.clear()


@router.message(TemplateEditStates.lesson_count, F.text, IsAdmin())
async def state_template_edit_lessons(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()

    if raw in {'', '-'}:
        lesson_count = None
    else:
        try:
            lesson_count = _parse_optional_positive_int(raw)
        except ValueError:
            await _discard_user_message(message)
            prompt = texts.PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT_EDIT.format(
                current=escape_html_text(data.get('original_lesson_count') or '—')
            )
            await _edit_flow_message(
                message.bot,
                data,
                message,
                _with_error(prompt, texts.PACKAGE_TEMPLATE_INVALID_NUMBER),
                markup,
            )
            await state.set_state(TemplateEditStates.lesson_count)
            return

    await state.update_data(edit_lesson_count=lesson_count)
    data = await state.get_data()
    await _discard_user_message(message)
    current_duration = data.get('original_duration_days')
    prompt = texts.PACKAGE_TEMPLATE_PROMPT_DURATION_EDIT.format(
        current=escape_html_text(current_duration or '—')
    )
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        prompt,
        markup,
    )
    await state.set_state(TemplateEditStates.duration_days)


@router.message(TemplateEditStates.duration_days, F.text, IsAdmin())
async def state_template_edit_duration(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()

    if raw in {'', '-'}:
        duration_days = None
    else:
        try:
            duration_days = _parse_optional_positive_int(raw)
        except ValueError:
            await _discard_user_message(message)
            prompt = texts.PACKAGE_TEMPLATE_PROMPT_DURATION_EDIT.format(
                current=escape_html_text(data.get('original_duration_days') or '—')
            )
            await _edit_flow_message(
                message.bot,
                data,
                message,
                _with_error(prompt, texts.PACKAGE_TEMPLATE_INVALID_NUMBER),
                markup,
            )
            await state.set_state(TemplateEditStates.duration_days)
            return

    await state.update_data(edit_duration_days=duration_days)
    data = await state.get_data()
    await _discard_user_message(message)
    current_timezone = data.get('original_timezone') or 'Europe/Moscow'
    prompt = texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE_EDIT.format(
        current=escape_html_text(current_timezone)
    )
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        prompt,
        markup,
    )
    await state.set_state(TemplateEditStates.timezone)


@router.message(TemplateEditStates.timezone, F.text, IsAdmin())
async def state_template_edit_timezone(message: types.Message, state: FSMContext, session: AsyncSession):
    raw = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    markup = _package_template_edit_cancel_keyboard(template_id).as_markup()

    if raw in {'', '-'}:
        tz_name = None
    else:
        try:
            ZoneInfo(raw)
        except Exception:
            await _discard_user_message(message)
            current_timezone = data.get('original_timezone') or 'Europe/Moscow'
            prompt = texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE_EDIT.format(
                current=escape_html_text(current_timezone)
            )
            await _edit_flow_message(
                message.bot,
                data,
                message,
                _with_error(prompt, texts.PACKAGE_EDIT_INVALID_TIMEZONE),
                markup,
            )
            await state.set_state(TemplateEditStates.timezone)
            return
        tz_name = raw

    await _discard_user_message(message)
    try:
        template = await template_service.get_template(session, template_id)
    except NotFoundError:
        await state.clear()
        await _safe_edit_message(
            message.bot,
            data.get('menu_chat_id', message.chat.id),
            data.get('menu_message_id', message.message_id),
            texts.PACKAGE_TEMPLATE_NOT_FOUND,
            markup,
        )
        return

    updates = {}
    if data.get('edit_name') is not None:
        updates['name'] = data['edit_name']
    if data.get('edit_description') is not None:
        updates['description'] = data['edit_description']
    if data.get('edit_lesson_count') is not None:
        updates['lesson_count'] = data['edit_lesson_count']
    if data.get('edit_duration_days') is not None:
        updates['duration_days'] = data['edit_duration_days']
    if tz_name is not None:
        updates['default_timezone'] = tz_name

    config = copy.deepcopy(template.default_config or {})
    schedule_update = data.get('edit_schedule')
    config_update = None
    if schedule_update is not None:
        config['weekly_schedule'] = schedule_update
        config_update = config

    try:
        await template_service.update_template(
            session,
            template_id,
            default_config=config_update,
            **updates,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update template %s: %s", template_id, exc, exc_info=True)
        current_timezone = escape_html_text((tz_name or template.timezone) or 'Europe/Moscow')
        prompt = texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE_EDIT.format(current=current_timezone)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(prompt, texts.DATABASE_ERROR),
            markup,
        )
        await state.set_state(TemplateEditStates.timezone)
        return

    template = await template_service.get_template(session, template_id)
    text = _format_template_details(template)
    detail_markup = _build_template_details_keyboard(template_id).as_markup()
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        text,
        detail_markup,
    )
    await _send_notice(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        texts.PACKAGE_UPDATED.format(title=escape_html_text(template.name)),
    )
    await state.clear()

@router.callback_query(F.data.startswith('packages_list:'), IsAdmin())
async def cb_packages_list(query: CallbackQuery, session: AsyncSession):
    try:
        _, page_str = query.data.split(':')
        page = int(page_str)
    except (ValueError, IndexError):
        page = 1

    limit = PACKAGES_PER_PAGE
    offset = max(0, (page - 1) * limit)
    packages, total = await package_service.list_packages(session, limit=limit, offset=offset)
    total_pages = _calc_total_pages(total, limit)
    if page > total_pages:
        page = total_pages
        offset = max(0, (page - 1) * limit)
        packages, total = await package_service.list_packages(session, limit=limit, offset=offset)

    text = _format_packages_list(packages, total, page)
    markup = _build_packages_keyboard(packages, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_view:'), IsAdmin())
async def cb_package_view(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    text = _format_package_details(package)
    markup = _build_package_details_keyboard(package_id, page).as_markup()
    await _safe_edit_message(query.bot, query.message.chat.id, query.message.message_id, text, markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_edit:'), IsAdmin())
async def cb_package_edit(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    original_schedule: list[dict[str, object]] = []
    if package.template_id:
        try:
            template = await template_service.get_template(session, package.template_id)
            original_schedule = copy.deepcopy((template.default_config or {}).get('weekly_schedule', []))
        except NotFoundError:
            original_schedule = []

    await state.set_state(PackageEditStates.status)
    await state.update_data(
        package_id=package_id,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
        original_schedule=original_schedule,
        total_lessons=package.total_lessons,
        original_timezone=package.timezone or 'Europe/Moscow',
    )

    markup = _build_package_status_keyboard(package_id, page).as_markup()
    await query.message.edit_text(texts.PACKAGE_EDIT_PROMPT_STATUS, reply_markup=markup)
    await query.answer()


def _parse_optional_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if raw in {'', '-'}:
        return None
    return datetime.strptime(raw, "%d.%m.%Y")


@router.message(PackageEditStates.start_date, F.text, IsAdmin())
async def state_package_edit_start(message: types.Message, state: FSMContext):
    raw = (message.text or '').strip()
    data = await state.get_data()
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _discard_user_message(message)

    try:
        start_date = _parse_optional_date(raw)
    except ValueError:
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_EDIT_PROMPT_START, texts.PACKAGE_EDIT_INVALID_DATE),
            markup,
        )
        await state.set_state(PackageEditStates.start_date)
        return

    await state.update_data(start_date=start_date.isoformat() if start_date else None)
    tz_markup = _package_edit_timezone_keyboard(data['package_id'], data['list_page']).as_markup()
    await _edit_flow_message(message.bot, data, message, texts.PACKAGE_EDIT_PROMPT_TIMEZONE, tz_markup)
    await state.set_state(PackageEditStates.timezone)


@router.message(PackageEditStates.timezone, F.text, IsAdmin())
async def state_package_edit_timezone(message: types.Message, state: FSMContext):
    tz_name = (message.text or '').strip() or 'Europe/Moscow'
    data = await state.get_data()
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _discard_user_message(message)
    try:
        ZoneInfo(tz_name)
    except Exception:
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_EDIT_PROMPT_TIMEZONE, texts.PACKAGE_EDIT_INVALID_TIMEZONE),
            markup,
        )
        await state.set_state(PackageEditStates.timezone)
        return

    await state.update_data(timezone=tz_name)
    await _edit_flow_message(message.bot, data, message, texts.PACKAGE_EDIT_PROMPT_NOTES, markup)
    await state.set_state(PackageEditStates.notes)


@router.callback_query(PackageEditStates.timezone, F.data.startswith('package_edit_tz:'), IsAdmin())
async def cb_package_edit_timezone_choice(query: CallbackQuery, state: FSMContext):
    try:
        _, package_id_str, page_str, tz_name = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    await state.update_data(timezone=tz_name)
    data = await state.get_data()
    markup = _package_edit_cancel_keyboard(package_id, page).as_markup()
    await _safe_edit_message(
        query.bot,
        data.get('menu_chat_id', query.message.chat.id),
        data.get('menu_message_id', query.message.message_id),
        texts.PACKAGE_EDIT_PROMPT_NOTES,
        markup,
    )
    await state.set_state(PackageEditStates.notes)
    await query.answer()


@router.callback_query(PackageEditStates.timezone, F.data.startswith('package_edit_tz_custom:'), IsAdmin())
async def cb_package_edit_timezone_custom(query: CallbackQuery, state: FSMContext):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    data = await state.get_data()
    markup = _package_edit_cancel_keyboard(package_id, page).as_markup()
    await _safe_edit_message(
        query.bot,
        data.get('menu_chat_id', query.message.chat.id),
        data.get('menu_message_id', query.message.message_id),
        texts.PACKAGE_EDIT_PROMPT_TIMEZONE,
        markup,
    )
    await query.answer('Введите часовой пояс вручную')


@router.message(PackageEditStates.notes, F.text, IsAdmin())
async def state_package_edit_notes(message: types.Message, state: FSMContext, session: AsyncSession):
    note_text = (message.text or '').strip()
    notes = None if note_text in {'', '-'} else note_text

    data = await state.get_data()
    package_id = data.get('package_id')
    list_page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    status = data.get('status')
    tz_name = data.get('timezone')

    markup = _package_edit_cancel_keyboard(data.get('package_id', 0), list_page).as_markup()
    await _discard_user_message(message)

    if not package_id or not status:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.DATABASE_ERROR, markup)
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    start_date_iso = data.get('start_date')
    original_schedule = data.get('original_schedule') or []
    total_lessons = data.get('total_lessons') or package.total_lessons
    lessons = await lesson_service.list_lessons(session, package_id)
    lessons_sorted = sorted(
        [lesson for lesson in lessons if lesson.scheduled_at],
        key=lambda l: l.scheduled_at,
    )

    start_dt = None
    if start_date_iso is not None:
        start_dt = datetime.fromisoformat(start_date_iso) if start_date_iso else None
    elif package.start_date is not None:
        start_dt = package.start_date
    if isinstance(start_dt, datetime) and start_dt and start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    if not start_dt and lessons_sorted:
        start_dt = lessons_sorted[0].scheduled_at
        if start_dt and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

    tz_effective = tz_name or package.timezone or 'Europe/Moscow'
    auto_end_dt = _compute_auto_end_date(start_dt, tz_effective, original_schedule, total_lessons)
    derived_end_dt = lessons_sorted[-1].scheduled_at if lessons_sorted else None
    if derived_end_dt and derived_end_dt.tzinfo is None:
        derived_end_dt = derived_end_dt.replace(tzinfo=timezone.utc)
    final_end_dt = auto_end_dt or derived_end_dt

    updates: dict[str, object] = {
        'status': status,
        'timezone_name': tz_name,
        'notes': notes,
    }
    if start_dt is not None or package.start_date is not None:
        updates['start_date'] = start_dt
    if final_end_dt is not None or package.end_date is not None:
        updates['end_date'] = final_end_dt

    changes = {}
    for key, value in updates.items():
        attr = key if key not in {'timezone_name'} else 'timezone'
        current = getattr(package, attr)
        if attr in {'start_date', 'end_date'} and isinstance(current, datetime) and current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if attr == 'notes':
            if (current or None) != value:
                changes[key] = value
        elif attr == 'timezone':
            if (current or 'Europe/Moscow') != value:
                changes[key] = value
        else:
            if current != value:
                changes[key] = value

    if not changes:
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_EDIT_PROMPT_NOTES, texts.PACKAGE_EDIT_NO_CHANGES),
            markup,
        )
        await state.set_state(PackageEditStates.notes)
        return

    try:
        await package_service.update_package(session, package_id, **changes)
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await _edit_flow_message(
            message.bot,
            data,
            message,
            texts.PACKAGE_NOT_FOUND,
            markup,
        )
        await state.clear()
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update package %s: %s", package_id, exc, exc_info=True)
        await _edit_flow_message(
            message.bot,
            data,
            message,
            _with_error(texts.PACKAGE_EDIT_PROMPT_NOTES, texts.DATABASE_ERROR),
            markup,
        )
        await state.set_state(PackageEditStates.notes)
        return

    package = await package_service.get_package(session, package_id)
    detail_text = _format_package_details(package)
    detail_markup = _build_package_details_keyboard(package_id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await _send_notice(
        message.bot,
        menu_chat_id,
        texts.PACKAGE_UPDATED_NOTICE,
    )
    await state.clear()


@router.callback_query(F.data.startswith('package_add_lesson:'), IsAdmin())
async def cb_package_add_lesson(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonCreateStates.scheduled_at)
    await state.update_data(
        package_id=package_id,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
    await _safe_edit_message(
        query.bot,
        query.message.chat.id,
        query.message.message_id,
        texts.PACKAGE_LESSON_PROMPT_DATETIME,
        markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_add_lesson_cancel:'), IsAdmin())
async def cb_package_add_lesson_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        package_id = None
        page = 1

    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)
    await state.clear()

    if package_id is not None:
        try:
            package = await package_service.get_package(session, package_id)
        except NotFoundError:
            package = None
        if package:
            detail_text = _format_package_details(package)
            detail_markup = _build_package_details_keyboard(package_id, page).as_markup()
            await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
            await query.answer(texts.PACKAGE_ADD_LESSON_CANCELLED)
            return

    markup = _packages_menu_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.ADMIN_PACKAGES_MENU, markup)
    await query.answer(texts.PACKAGE_ADD_LESSON_CANCELLED)


@router.message(LessonCreateStates.scheduled_at, F.text, IsAdmin())
async def state_package_add_lesson(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    package_id = data.get('package_id')
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    await _discard_user_message(message)

    if not package_id:
        await state.clear()
        markup = _package_add_lesson_cancel_keyboard(package_id or 0, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await state.clear()
        markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    tz = ZoneInfo(package.timezone or 'Europe/Moscow')
    raw_text = (message.text or '').strip()
    try:
        local_dt = _parse_lesson_datetime(raw_text, tz)
    except ValueError:
        markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(texts.PACKAGE_LESSON_PROMPT_DATETIME, texts.PACKAGE_LESSON_INVALID_DATETIME),
            markup,
        )
        await state.set_state(LessonCreateStates.scheduled_at)
        return

    scheduled_at = local_dt.astimezone(timezone.utc)
    await state.update_data(scheduled_at_iso=scheduled_at.isoformat())

    markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_LESSON_PROMPT_DURATION, markup)
    await state.set_state(LessonCreateStates.duration)

@router.message(LessonCreateStates.duration, F.text, IsAdmin())
async def state_package_add_duration(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    package_id = data.get('package_id')
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    scheduled_at_iso = data.get('scheduled_at_iso')

    await _discard_user_message(message)

    if not package_id or not scheduled_at_iso:
        await state.clear()
        markup = _package_add_lesson_cancel_keyboard(package_id or 0, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    duration_text = (message.text or '').strip()
    if duration_text in {'', '-'}:
        duration = None
    else:
        if not duration_text.isdigit() or int(duration_text) <= 0:
            markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
            await _safe_edit_message(
                message.bot,
                menu_chat_id,
                menu_message_id,
                _with_error(texts.PACKAGE_LESSON_PROMPT_DURATION, texts.PACKAGE_LESSON_INVALID_DURATION),
                markup,
            )
            await state.set_state(LessonCreateStates.duration)
            return
        duration = int(duration_text)

    scheduled_at = datetime.fromisoformat(scheduled_at_iso).replace(tzinfo=timezone.utc)
    try:
        existing = await lesson_service.list_lessons(session, package_id)
    except NotFoundError:
        await state.clear()
        markup = _package_add_lesson_cancel_keyboard(package_id or 0, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return
    existing_indices = [lesson.sequence_index for lesson in existing if lesson.sequence_index is not None]
    if existing_indices:
        sequence_index = max(existing_indices) + 1
    else:
        sequence_index = len(existing) + 1

    try:
        await lesson_service.create_lesson(
            session,
            package_id=package_id,
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            sequence_index=sequence_index,
        )
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        await state.clear()
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to add lesson to package %s: %s", package_id, exc, exc_info=True)
        markup = _package_add_lesson_cancel_keyboard(package_id, page).as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.DATABASE_ERROR, markup)
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await state.clear()
        markup = _packages_menu_keyboard().as_markup()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    detail_text = f"{texts.PACKAGE_LESSON_CREATED_NOTICE}\n\n{_format_package_details(package)}"
    detail_markup = _build_package_details_keyboard(package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await state.clear()
@router.callback_query(F.data.startswith('package_lesson_edit:'), IsAdmin())
async def cb_package_lesson_edit(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonEditStates.scheduled_at)
    await state.update_data(
        package_id=package_id,
        lesson_id=lesson_id,
        lesson_index=lesson_index,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_lesson_edit_cancel_keyboard(package_id, page).as_markup()
    await _edit_flow_message(
        query.bot,
        {
            'menu_chat_id': query.message.chat.id,
            'menu_message_id': query.message.message_id,
        },
        query.message,
        texts.PACKAGE_LESSON_EDIT_PROMPT.format(index=lesson_index),
        markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_status:'), IsAdmin())
async def cb_package_lesson_status(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonStatusStates.value)
    await state.update_data(
        package_id=package_id,
        lesson_id=lesson_id,
        lesson_index=lesson_index,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _lesson_status_keyboard(package_id, lesson_id, lesson_index, page).as_markup()
    await _safe_edit_message(
        query.bot,
        query.message.chat.id,
        query.message.message_id,
        texts.PACKAGE_LESSON_PROMPT_STATUS_INLINE.format(index=lesson_index),
        markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_notes:'), IsAdmin())
async def cb_package_lesson_notes(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonNotesStates.value)
    await state.update_data(
        package_id=package_id,
        lesson_id=lesson_id,
        lesson_index=lesson_index,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_lesson_edit_cancel_keyboard(package_id, page).as_markup()
    await query.message.edit_text(
        texts.PACKAGE_LESSON_PROMPT_NOTES.format(index=lesson_index),
        reply_markup=markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_duration:'), IsAdmin())
async def cb_package_lesson_duration(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonDurationStates.value)
    await state.update_data(
        package_id=package_id,
        lesson_id=lesson_id,
        lesson_index=lesson_index,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_lesson_edit_cancel_keyboard(package_id, page).as_markup()
    await query.message.edit_text(
        texts.PACKAGE_LESSON_PROMPT_DURATION_EDIT.format(index=lesson_index),
        reply_markup=markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_delete_confirm:'), IsAdmin())
async def cb_package_lesson_delete_confirm(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    scheduled = format_timestamp_msk(lesson.scheduled_at) if lesson.scheduled_at else '—'
    status = lesson.status or 'scheduled'
    builder = InlineKeyboardBuilder()
    builder.button(
        text='✅ Да, удалить',
        callback_data=f'package_lesson_delete:{package_id}:{lesson_id}:{lesson_index}:{page}'
    )
    builder.button(text='⬅️ Назад', callback_data=f'package_lessons:{package_id}:{page}')
    builder.adjust(1)
    await query.message.edit_text(
        texts.PACKAGE_LESSON_ITEM.format(
            index=lesson_index,
            scheduled=escape_html_text(scheduled),
            status=escape_html_text(status),
        ) + '\n\nУдалить этот урок?',
        reply_markup=builder.as_markup(),
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_delete:'), IsAdmin())
async def cb_package_lesson_delete(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    if lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    try:
        await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    try:
        await lesson_service.delete_lesson(session, lesson_id)
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to delete lesson %s from package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    package = await package_service.get_package(session, package_id)
    lessons = await lesson_service.list_lessons(session, package_id)
    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_LESSON_DELETED.format(index=lesson_index))


@router.callback_query(F.data.startswith('package_lesson_edit_cancel:'), IsAdmin())
async def cb_package_lesson_edit_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        package_id = None
        page = 1

    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)
    lesson_id = data.get('lesson_id')
    lesson_index = int(data.get('lesson_index', 1))
    await state.clear()

    if package_id:
        try:
            package = await package_service.get_package(session, package_id)
        except NotFoundError:
            package = None
        if package and lesson_id:
            try:
                lesson = await lesson_service.get_lesson(session, lesson_id)
            except NotFoundError:
                lesson = None
            if lesson and lesson.package_id == package_id:
                await _show_lesson_detail(
                    query.bot,
                    {'menu_chat_id': menu_chat_id, 'menu_message_id': menu_message_id},
                    query.message,
                    package,
                    lesson,
                    lesson_index,
                    page,
                )
                await query.answer(texts.PACKAGE_LESSON_EDIT_CANCELLED)
                return

        if package:
            lessons = await lesson_service.list_lessons(session, package.id)
            text = _format_lessons_list(lessons, package_title=package.title)
            markup = _build_lessons_keyboard(lessons, package.id, page).as_markup()
            await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, text, markup)
            await query.answer(texts.PACKAGE_LESSON_EDIT_CANCELLED)
            return

    markup = _packages_menu_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.ADMIN_PACKAGES_MENU, markup)
    await query.answer(texts.PACKAGE_LESSON_EDIT_CANCELLED)


@router.message(LessonEditStates.scheduled_at, F.text, IsAdmin())
async def state_package_lesson_edit(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    cancel_package_id = package_id or data.get('package_id') or 0
    markup = _package_lesson_edit_cancel_keyboard(cancel_package_id, page).as_markup()

    raw_text = (message.text or '').strip()
    await _discard_user_message(message)

    if not package_id or not lesson_id:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    try:
        local_dt = datetime.strptime(raw_text, "%d.%m.%Y %H:%M")
    except ValueError:
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(texts.PACKAGE_LESSON_PROMPT_DATETIME, texts.PACKAGE_LESSON_INVALID_DATETIME),
            markup,
        )
        await state.set_state(LessonEditStates.scheduled_at)
        return

    tz = ZoneInfo(package.timezone or 'Europe/Moscow')
    scheduled_at = local_dt.replace(tzinfo=tz).astimezone(timezone.utc)

    try:
        await lesson_service.update_lesson(
            session,
            lesson_id,
            scheduled_at=scheduled_at,
        )
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        await state.clear()
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(texts.PACKAGE_LESSON_PROMPT_DATETIME, texts.DATABASE_ERROR),
            markup,
        )
        await state.set_state(LessonEditStates.scheduled_at)
        return

    package = await package_service.get_package(session, package_id)
    lessons = await lesson_service.list_lessons(session, package_id)
    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await _send_notice(
        message.bot,
        menu_chat_id,
        texts.PACKAGE_LESSON_UPDATED.format(index=lesson_index),
    )
    await state.clear()


@router.callback_query(F.data.startswith('package_lesson_status_set:'), IsAdmin())
async def cb_package_lesson_status_set(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str, status = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        lesson_index = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    if await state.get_state() != LessonStatusStates.value.state:
        await query.answer()
        return

    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', query.message.chat.id)
    menu_message_id = data.get('menu_message_id', query.message.message_id)

    try:
        await lesson_service.update_lesson(
            session,
            lesson_id,
            status=status,
        )
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await state.clear()
        await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, _package_lesson_edit_cancel_keyboard(package_id, page).as_markup())
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson status %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await _safe_edit_message(
            query.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(
                texts.PACKAGE_LESSON_PROMPT_STATUS_INLINE.format(index=lesson_index),
                texts.DATABASE_ERROR,
            ),
            _package_lesson_edit_cancel_keyboard(package_id, page).as_markup(),
        )
        await state.set_state(LessonStatusStates.value)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    package = await package_service.get_package(session, package_id)
    lessons = await lesson_service.list_lessons(session, package_id)

    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, text, markup)
    await _send_notice(
        query.bot,
        menu_chat_id,
        texts.PACKAGE_LESSON_STATUS_UPDATED.format(index=lesson_index),
    )
    await state.clear()
    await query.answer(texts.PACKAGE_LESSON_STATUS_UPDATED.format(index=lesson_index))


@router.message(LessonStatusStates.value, F.text, IsAdmin())
async def state_package_lesson_status_text(message: types.Message, state: FSMContext):
    await _discard_user_message(message)
    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    if not package_id or not lesson_id:
        await state.clear()
        return

    markup = _lesson_status_keyboard(package_id, lesson_id, lesson_index, page).as_markup()
    await _safe_edit_message(
        message.bot,
        data.get('menu_chat_id', message.chat.id),
        data.get('menu_message_id', message.message_id),
        texts.PACKAGE_LESSON_PROMPT_STATUS_INLINE.format(index=lesson_index),
        markup,
    )
@router.message(LessonNotesStates.value, F.text, IsAdmin())
async def state_package_lesson_notes(message: types.Message, state: FSMContext, session: AsyncSession):
    note_text = (message.text or '').strip()
    notes = None if note_text in {'', '-'} else note_text

    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    cancel_package_id = package_id or data.get('package_id') or 0
    markup = _package_lesson_edit_cancel_keyboard(cancel_package_id, page).as_markup()
    await _discard_user_message(message)

    if not package_id or not lesson_id:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    try:
        await lesson_service.update_lesson(
            session,
            lesson_id,
            teacher_notes=notes,
        )
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson notes %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(texts.PACKAGE_LESSON_PROMPT_NOTES.format(index=lesson_index), texts.DATABASE_ERROR),
            markup,
        )
        await state.set_state(LessonNotesStates.value)
        return

    package = await package_service.get_package(session, package_id)
    lessons = await lesson_service.list_lessons(session, package_id)
    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await _send_notice(
        message.bot,
        menu_chat_id,
        texts.PACKAGE_LESSON_NOTES_UPDATED.format(index=lesson_index),
    )
    await state.clear()


@router.message(LessonDurationStates.value, F.text, IsAdmin())
async def state_package_lesson_duration(message: types.Message, state: FSMContext, session: AsyncSession):
    duration_text = (message.text or '').strip()
    if duration_text in {'', '-'}:
        duration = None
    else:
        if not duration_text.isdigit() or int(duration_text) <= 0:
            data = await state.get_data()
            package_id = data.get('package_id')
            page = int(data.get('list_page', 1))
            cancel_package_id = package_id or data.get('package_id') or 0
            markup = _package_lesson_edit_cancel_keyboard(cancel_package_id, page).as_markup()
            await _discard_user_message(message)
            await _safe_edit_message(
                message.bot,
                data.get('menu_chat_id', message.chat.id),
                data.get('menu_message_id', message.message_id),
                _with_error(
                    texts.PACKAGE_LESSON_PROMPT_DURATION_EDIT.format(
                        index=data.get('lesson_index', 1)
                    ),
                    texts.PACKAGE_LESSON_INVALID_DURATION,
                ),
                markup,
            )
            await state.set_state(LessonDurationStates.value)
            return
        duration = int(duration_text)

    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    markup = _package_lesson_edit_cancel_keyboard(package_id or 0, page).as_markup()
    await _discard_user_message(message)

    if not package_id or not lesson_id:
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return

    try:
        await lesson_service.update_lesson(
            session,
            lesson_id,
            duration_minutes=duration,
        )
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await state.clear()
        await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_NOT_FOUND, markup)
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson duration %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await _safe_edit_message(
            message.bot,
            menu_chat_id,
            menu_message_id,
            _with_error(
                texts.PACKAGE_LESSON_PROMPT_DURATION_EDIT.format(index=lesson_index),
                texts.DATABASE_ERROR,
            ),
            markup,
        )
        await state.set_state(LessonDurationStates.value)
        return

    package = await package_service.get_package(session, package_id)
    lessons = await lesson_service.list_lessons(session, package_id)
    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await _send_notice(
        message.bot,
        menu_chat_id,
        texts.PACKAGE_LESSON_DURATION_UPDATED.format(index=lesson_index),
    )
    await state.clear()
@router.callback_query(F.data.startswith('package_regenerate:'), IsAdmin())
async def cb_package_regenerate(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package_dto = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    try:
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
        await query.answer(texts.PACKAGE_REGENERATED.format(title=escape_html_text(package_dto.title)))
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to regenerate reminders for package %s: %s", package_id, exc, exc_info=True)
        await query.answer(texts.PACKAGE_REGENERATE_FAILED.format(error=escape_html_text(str(exc))), show_alert=True)
        return

    # Refresh package details after regeneration
    package = await package_service.get_package(session, package_id)
    text = _format_package_details(package)
    markup = _build_package_details_keyboard(package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith('package_delete_confirm:'), IsAdmin())
async def cb_package_delete_confirm(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text='✅ Да, удалить', callback_data=f'package_delete:{package_id}:{page}')
    builder.button(text='⬅️ Назад', callback_data=f'package_view:{package_id}:{page}')
    builder.adjust(1)
    await query.message.edit_text(
        texts.PACKAGE_DELETE_CONFIRM.format(title=escape_html_text(package.title)),
        reply_markup=builder.as_markup(),
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_delete:'), IsAdmin())
async def cb_package_delete(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    try:
        await package_service.delete_package(session, package_id)
        await session.commit()
    except NotFoundError:
        await session.rollback()
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to delete package %s: %s", package_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    limit = PACKAGES_PER_PAGE
    offset = max(0, (page - 1) * limit)
    packages, total = await package_service.list_packages(session, limit=limit, offset=offset)
    total_pages = _calc_total_pages(total, limit)
    if page > total_pages:
        page = total_pages
        offset = max(0, (page - 1) * limit)
        packages, total = await package_service.list_packages(session, limit=limit, offset=offset)

    text = _format_packages_list(packages, total, page)
    markup = _build_packages_keyboard(packages, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_DELETED)


@router.callback_query(F.data.startswith('package_lessons:'), IsAdmin())
async def cb_package_lessons(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    lessons = await lesson_service.list_lessons(session, package_id)
    text = _format_lessons_list(lessons, package_title=package.title)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_view:'), IsAdmin())
async def cb_package_lesson_view(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, lesson_id_str, index_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        lesson_id = int(lesson_id_str)
        idx = int(index_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        package = await package_service.get_package(session, package_id)
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    if lesson.package_id != package_id:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    await _show_lesson_detail(
        query.bot,
        {
            'menu_chat_id': query.message.chat.id,
            'menu_message_id': query.message.message_id,
        },
        query.message,
        package,
        lesson,
        idx,
        page,
    )
    await query.answer()
