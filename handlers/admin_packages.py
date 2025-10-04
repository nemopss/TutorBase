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
from filters.admin import IsAdmin
from services.package_scheduler import regenerate_package_reminders
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
    end_date = State()
    timezone = State()
    notes = State()


class TemplateCreateStates(StatesGroup):
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


def _calc_total_pages(total: int, per_page: int) -> int:
    if total <= 0:
        return 1
    return max(1, (total + per_page - 1) // per_page)


async def _safe_edit_message(bot, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
    except TelegramBadRequest:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)


def _format_package_period(package) -> str:
    start = escape_html_text(format_timestamp_msk(package.start_date)) if package.start_date else texts.PACKAGE_PERIOD_UNKNOWN
    end = escape_html_text(format_timestamp_msk(package.end_date)) if package.end_date else texts.PACKAGE_PERIOD_UNKNOWN
    return f"{start} — {end}"


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


def _package_template_cancel_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data='package_template_cancel')
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


async def _generate_lessons_from_template(
    session: AsyncSession,
    package,
    template,
    start_date: datetime,
) -> None:
    config = template.default_config or {}
    schedule = config.get('weekly_schedule') or []
    if not schedule:
        return

    lesson_limit = template.lesson_count or len(schedule)
    tz = ZoneInfo(package.timezone or template.default_timezone or 'Europe/Moscow')
    base_date = start_date.astimezone(tz)

    heap: list[tuple[datetime, dict[str, object]]] = []
    for item in schedule:
        day = item.get('day')
        time_str = item.get('time')
        if not isinstance(day, int) or not isinstance(time_str, str):
            continue
        lesson_time = parse_time(time_str)
        days_delta = (day - base_date.weekday()) % 7
        candidate = base_date + timedelta(days=days_delta)
        candidate = candidate.replace(hour=lesson_time.hour, minute=lesson_time.minute, second=0, microsecond=0)
        if candidate < base_date:
            candidate += timedelta(days=7)
        heapq.heappush(heap, (candidate, {'day': day, 'time': time_str}))

    created_lessons = []
    sequence = 1
    while heap and len(created_lessons) < lesson_limit:
        candidate, item = heapq.heappop(heap)
        scheduled_utc = candidate.astimezone(timezone.utc)
        await crud.create_lesson(
            session,
            package,
            scheduled_at=scheduled_utc,
            sequence_index=sequence,
            duration_minutes=None,
        )
        created_lessons.append(scheduled_utc)
        sequence += 1
        candidate += timedelta(days=7)
        if len(created_lessons) < lesson_limit:
            heapq.heappush(heap, (candidate, item))

    if created_lessons:
        last_lesson = created_lessons[-1]
        await crud.update_lesson_package(
            session,
            package,
            total_lessons=len(created_lessons),
            end_date=last_lesson,
        )


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
        label = f"📦 {package.title} — {package.learner.display_name if package.learner else '—'}"
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
        learner = package.learner.display_name if package.learner else '—'
        lines.append(
            texts.PACKAGES_LIST_ITEM.format(
                index=idx,
                title=escape_html_text(package.title),
                learner=escape_html_text(learner),
                status=escape_html_text(package.status),
            )
        )
    return '\n'.join(lines)


def _format_package_details(package) -> str:
    period = _format_package_period(package)
    notes = escape_html_text(package.notes or '—')
    lesson_count = len(package.lessons or [])
    learner = package.learner.display_name if package.learner else '—'
    return texts.PACKAGE_DETAILS.format(
        title=escape_html_text(package.title),
        learner=escape_html_text(learner),
        status=escape_html_text(package.status),
        lessons=escape_html_text(lesson_count),
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
    builder.button(text='⬅️ Назад', callback_data=f'packages_list:{page}')
    builder.adjust(1)
    return builder


def _format_lessons_list(lessons) -> str:
    if not lessons:
        return texts.PACKAGE_LESSONS_EMPTY
    first_package = lessons[0].package if lessons[0].package else None
    title = escape_html_text(first_package.title) if first_package else '—'
    lines = [texts.PACKAGE_LESSONS_HEADER.format(title=title), '']
    for idx, lesson in enumerate(lessons, start=1):
        scheduled = format_timestamp_msk(lesson.scheduled_at) if lesson.scheduled_at else '—'
        duration = f" ({lesson.duration_minutes} мин)" if lesson.duration_minutes else ''
        lines.append(
            texts.PACKAGE_LESSON_ITEM.format(
                index=idx,
                scheduled=escape_html_text(scheduled + duration),
                status=escape_html_text(lesson.status or 'scheduled'),
            )
        )
    return '\n'.join(lines)


def _build_lessons_keyboard(lessons, package_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for idx, lesson in enumerate(lessons, start=1):
        builder.button(text=f'🕒#{idx}', callback_data=f'package_lesson_edit:{package_id}:{lesson.id}:{idx}:{page}')
        builder.button(text=f'⏱#{idx}', callback_data=f'package_lesson_duration:{package_id}:{lesson.id}:{idx}:{page}')
        builder.button(text=f'📊#{idx}', callback_data=f'package_lesson_status:{package_id}:{lesson.id}:{idx}:{page}')
        builder.button(text=f'📝#{idx}', callback_data=f'package_lesson_notes:{package_id}:{lesson.id}:{idx}:{page}')
        builder.button(text=f'🗑#{idx}', callback_data=f'package_lesson_delete_confirm:{package_id}:{lesson.id}:{idx}:{page}')
    if lessons:
        builder.adjust(5)

    builder.row(InlineKeyboardButton(text='➕ Добавить урок', callback_data=f'package_add_lesson:{package_id}:{page}'))
    builder.row(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'package_view:{package_id}:{page}'))
    return builder


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
    timezone_name = escape_html_text(template.default_timezone or 'Europe/Moscow')
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
    builder.button(text='🗑 Удалить', callback_data=f'package_template_delete_confirm:{template_id}')
    builder.button(text='⬅️ Назад', callback_data='package_templates')
    builder.adjust(1)
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
    templates = await crud.fetch_lesson_package_templates(session)
    text = _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await query.message.edit_text(texts.PACKAGE_TEMPLATES_MENU + '\n\n' + text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_template_view'), IsAdmin())
async def cb_package_template_view(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
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


@router.callback_query(F.data.startswith('package_template_delete_confirm'), IsAdmin())
async def cb_package_template_delete_confirm(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
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


@router.callback_query(F.data.startswith('package_template_delete'), IsAdmin())
async def cb_package_template_delete(query: CallbackQuery, session: AsyncSession):
    try:
        _, template_id_str = query.data.split(':')
        template_id = int(template_id_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
        await query.answer(texts.PACKAGE_TEMPLATE_NOT_FOUND, show_alert=True)
        return

    try:
        await crud.delete_lesson_package_template(session, template)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to delete template %s: %s", template_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    templates = await crud.fetch_lesson_package_templates(session)
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
    templates = await crud.fetch_lesson_package_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, text, markup)
    await query.answer(texts.PACKAGE_TEMPLATE_CANCELLED)
@router.callback_query(F.data == 'package_create', IsAdmin())
async def cb_package_create(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    learners, total, total_pages, page = await _load_learners_page(session, 1)
    if total == 0 or not learners:
        await query.answer(texts.PACKAGE_CREATE_NO_LEARNERS, show_alert=True)
        return

    await state.set_state(PackageCreateStates.selecting_learner)
    await state.update_data(
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
        list_page=1,
    )

    text = _format_learners_list(learners, total)
    markup = _build_package_learners_keyboard(learners, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(PackageCreateStates.selecting_learner, F.data.startswith('package_create_page'), IsAdmin())
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


@router.callback_query(PackageCreateStates.selecting_learner, F.data.startswith('package_create_select'), IsAdmin())
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

    templates = await crud.fetch_lesson_package_templates(session)
    await state.update_data(
        learner_id=learner_id,
        learner_name=learner.display_name,
        list_page=page,
        template_id=None,
        template_name=None,
    )

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


@router.callback_query(PackageCreateStates.selecting_template, F.data.startswith('package_create_template'), IsAdmin())
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

    template = await crud.get_lesson_package_template(session, template_id)
    if not template:
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


@router.callback_query(F.data.startswith('package_edit_cancel'), IsAdmin())
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
        package = await crud.get_lesson_package(session, package_id)
        if package:
            detail_text = _format_package_details(package)
            detail_markup = _build_package_details_keyboard(package_id, page).as_markup()
            await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
            await query.answer(texts.PACKAGE_EDIT_CANCELLED)
            return

    markup = _packages_menu_keyboard().as_markup()
    await _safe_edit_message(query.bot, menu_chat_id, menu_message_id, texts.ADMIN_PACKAGES_MENU, markup)
    await query.answer(texts.PACKAGE_EDIT_CANCELLED)


@router.message(PackageCreateStates.title, F.text, IsAdmin())
async def state_package_title(message: types.Message, state: FSMContext):
    title = (message.text or '').strip()
    data = await state.get_data()
    template_id = data.get('template_id')
    template_name = data.get('template_name')
    if template_id:
        if title in {'', '-'}:
            title = template_name
    if not title:
        prompt = texts.PACKAGE_PROMPT_TITLE_TEMPLATE.format(default=escape_html_text(template_name)) if template_id else texts.PACKAGE_PROMPT_TITLE
        await message.answer(prompt)
        return

    await state.update_data(title=title)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_create_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_PROMPT_NOTES, markup)
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

    if not learner_id or not title:
        await state.clear()
        await message.answer(texts.DATABASE_ERROR)
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
        await message.answer(texts.LEARNER_NOT_FOUND)
        return

    try:
        package = await crud.create_lesson_package(
            session,
            learner=learner,
            title=title,
            notes=notes,
        )
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create package: %s", exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    package = await crud.get_lesson_package(session, package.id)
    detail_text = _format_package_details(package)
    detail_markup = _build_package_details_keyboard(package.id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await message.answer(texts.PACKAGE_CREATED.format(title=escape_html_text(package.title)))
    await state.clear()


@router.message(PackageCreateStates.template_start_date, F.text, IsAdmin())
async def state_package_template_start_date(message: types.Message, state: FSMContext, session: AsyncSession):
    raw = (message.text or '').strip()
    try:
        start_date_value = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(texts.PACKAGE_TEMPLATE_INVALID_DATE)
        return

    data = await state.get_data()
    learner_id = data.get('learner_id')
    template_id = data.get('template_id')
    title = data.get('title')
    notes = data.get('notes')
    list_page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    learner = await crud.get_learner(session, learner_id)
    template = await crud.get_lesson_package_template(session, template_id)
    if not learner or not template:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    timezone_name = template.default_timezone or 'Europe/Moscow'
    tz = ZoneInfo(timezone_name)
    start_local = datetime.combine(start_date_value, time.min, tz)
    start_utc = start_local.astimezone(timezone.utc)

    try:
        package = await crud.create_lesson_package(
            session,
            learner=learner,
            template=template,
            title=title,
            notes=notes,
            start_date=start_utc,
            timezone_name=timezone_name,
            total_lessons=template.lesson_count,
        )
        await _generate_lessons_from_template(session, package, template, start_local)
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create package from template %s: %s", template_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    package = await crud.get_lesson_package(session, package.id)
    detail_text = _format_package_details(package)
    detail_markup = _build_package_details_keyboard(package.id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await message.answer(texts.PACKAGE_CREATED.format(title=escape_html_text(package.title)))
    await state.clear()


@router.message(TemplateCreateStates.name, F.text, IsAdmin())
async def state_template_name(message: types.Message, state: FSMContext):
    name = (message.text or '').strip()
    if not name:
        await message.answer(texts.PACKAGE_TEMPLATE_PROMPT_NAME)
        return
    await state.update_data(name=name)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_DESCRIPTION, markup)
    await state.set_state(TemplateCreateStates.description)


@router.message(TemplateCreateStates.description, F.text, IsAdmin())
async def state_template_description(message: types.Message, state: FSMContext):
    description = (message.text or '').strip()
    await state.update_data(description=None if description in {'', '-'} else description)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_SCHEDULE, markup)
    await state.set_state(TemplateCreateStates.schedule)


@router.message(TemplateCreateStates.schedule, F.text, IsAdmin())
async def state_template_schedule(message: types.Message, state: FSMContext):
    raw = message.text or ''
    try:
        schedule = _parse_schedule_input(raw)
    except ValueError:
        await message.answer(texts.PACKAGE_TEMPLATE_INVALID_SCHEDULE)
        return

    await state.update_data(schedule=schedule)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_LESSON_COUNT, markup)
    await state.set_state(TemplateCreateStates.lesson_count)


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
    raw = message.text or ''
    try:
        lesson_count = _parse_optional_positive_int(raw)
    except ValueError:
        await message.answer(texts.PACKAGE_TEMPLATE_INVALID_NUMBER)
        return
    await state.update_data(lesson_count=lesson_count)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_DURATION, markup)
    await state.set_state(TemplateCreateStates.duration_days)


@router.message(TemplateCreateStates.duration_days, F.text, IsAdmin())
async def state_template_duration(message: types.Message, state: FSMContext):
    raw = message.text or ''
    try:
        duration_days = _parse_optional_positive_int(raw)
    except ValueError:
        await message.answer(texts.PACKAGE_TEMPLATE_INVALID_NUMBER)
        return
    await state.update_data(duration_days=duration_days)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_template_cancel_keyboard().as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_TEMPLATE_PROMPT_TIMEZONE, markup)
    await state.set_state(TemplateCreateStates.timezone)


@router.message(TemplateCreateStates.timezone, F.text, IsAdmin())
async def state_template_timezone(message: types.Message, state: FSMContext, session: AsyncSession):
    tz_name = (message.text or '').strip() or 'Europe/Moscow'
    try:
        ZoneInfo(tz_name)
    except Exception:
        await message.answer(texts.PACKAGE_EDIT_INVALID_TIMEZONE)
        return

    data = await state.get_data()
    name = data.get('name')
    description = data.get('description')
    lesson_count = data.get('lesson_count')
    duration_days = data.get('duration_days')
    schedule = data.get('schedule') or []
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    try:
        template = await crud.create_lesson_package_template(
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
        await message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    templates = await crud.fetch_lesson_package_templates(session)
    text = texts.PACKAGE_TEMPLATES_MENU + '\n\n' + _format_templates_list(templates, len(templates))
    markup = _build_templates_keyboard(templates).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await message.answer(texts.PACKAGE_TEMPLATE_CREATED.format(name=escape_html_text(template.name)))
    await state.clear()

@router.callback_query(F.data.startswith('packages_list'), IsAdmin())
async def cb_packages_list(query: CallbackQuery, session: AsyncSession):
    try:
        _, page_str = query.data.split(':')
        page = int(page_str)
    except (ValueError, IndexError):
        page = 1

    limit = PACKAGES_PER_PAGE
    offset = max(0, (page - 1) * limit)
    packages, total = await crud.fetch_lesson_packages_paginated(session, limit=limit, offset=offset)
    total_pages = _calc_total_pages(total, limit)
    if page > total_pages:
        page = total_pages
        offset = max(0, (page - 1) * limit)
        packages, total = await crud.fetch_lesson_packages_paginated(session, limit=limit, offset=offset)

    text = _format_packages_list(packages, total, page)
    markup = _build_packages_keyboard(packages, page, total_pages).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_view'), IsAdmin())
async def cb_package_view(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    text = _format_package_details(package)
    markup = _build_package_details_keyboard(package_id, page).as_markup()
    await _safe_edit_message(query.bot, query.message.chat.id, query.message.message_id, text, markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_edit'), IsAdmin())
async def cb_package_edit(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    await state.set_state(PackageEditStates.status)
    await state.update_data(
        package_id=package_id,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_edit_cancel_keyboard(package_id, page).as_markup()
    await query.message.edit_text(texts.PACKAGE_EDIT_PROMPT_STATUS, reply_markup=markup)
    await query.answer()


@router.message(PackageEditStates.status, F.text, IsAdmin())
async def state_package_edit_status(message: types.Message, state: FSMContext):
    status = (message.text or '').strip().lower()
    if status not in {'draft', 'active', 'completed', 'cancelled'}:
        await message.answer(texts.PACKAGE_EDIT_INVALID_STATUS)
        return

    await state.update_data(status=status)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_EDIT_PROMPT_START, markup)
    await state.set_state(PackageEditStates.start_date)


def _parse_optional_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if raw in {'', '-'}:
        return None
    return datetime.strptime(raw, "%d.%m.%Y")


@router.message(PackageEditStates.start_date, F.text, IsAdmin())
async def state_package_edit_start(message: types.Message, state: FSMContext):
    raw = message.text or ''
    try:
        start_date = _parse_optional_date(raw)
    except ValueError:
        await message.answer(texts.PACKAGE_EDIT_INVALID_DATE)
        return

    await state.update_data(start_date=start_date)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_EDIT_PROMPT_END, markup)
    await state.set_state(PackageEditStates.end_date)


@router.message(PackageEditStates.end_date, F.text, IsAdmin())
async def state_package_edit_end(message: types.Message, state: FSMContext):
    raw = message.text or ''
    try:
        end_date = _parse_optional_date(raw)
    except ValueError:
        await message.answer(texts.PACKAGE_EDIT_INVALID_DATE)
        return

    await state.update_data(end_date=end_date)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_EDIT_PROMPT_TIMEZONE, markup)
    await state.set_state(PackageEditStates.timezone)


@router.message(PackageEditStates.timezone, F.text, IsAdmin())
async def state_package_edit_timezone(message: types.Message, state: FSMContext):
    tz_name = (message.text or '').strip() or 'Europe/Moscow'
    try:
        ZoneInfo(tz_name)
    except Exception:
        await message.answer(texts.PACKAGE_EDIT_INVALID_TIMEZONE)
        return

    await state.update_data(timezone=tz_name)
    data = await state.get_data()
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)
    markup = _package_edit_cancel_keyboard(data['package_id'], data['list_page']).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, texts.PACKAGE_EDIT_PROMPT_NOTES, markup)
    await state.set_state(PackageEditStates.notes)


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
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    tz_name = data.get('timezone')

    if not package_id or not status:
        await state.clear()
        await message.answer(texts.DATABASE_ERROR)
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    start_dt = None
    if isinstance(start_date, datetime):
        start_dt = start_date.replace(tzinfo=timezone.utc)
    elif start_date is None:
        start_dt = None

    end_dt = None
    if isinstance(end_date, datetime):
        end_dt = end_date.replace(tzinfo=timezone.utc)
    elif end_date is None:
        end_dt = None

    updates: dict[str, object] = {
        'status': status,
        'timezone_name': tz_name,
        'notes': notes,
    }
    if start_date is not None or package.start_date is not None:
        updates['start_date'] = start_dt
    if end_date is not None or package.end_date is not None:
        updates['end_date'] = end_dt

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
        await state.clear()
        await message.answer(texts.PACKAGE_EDIT_NO_CHANGES)
        return

    try:
        await crud.update_lesson_package(session, package, **changes)
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update package %s: %s", package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    package = await crud.get_lesson_package(session, package_id)
    detail_text = _format_package_details(package)
    detail_markup = _build_package_details_keyboard(package_id, list_page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await message.answer(texts.PACKAGE_UPDATED.format(title=escape_html_text(package.title)))
    await state.clear()


@router.callback_query(F.data.startswith('package_add_lesson'), IsAdmin())
async def cb_package_add_lesson(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    await state.set_state(LessonCreateStates.scheduled_at)
    await state.update_data(
        package_id=package_id,
        list_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )

    markup = _package_lesson_edit_cancel_keyboard(package_id, page).as_markup()
    await query.message.edit_text(texts.PACKAGE_LESSON_PROMPT_DATETIME, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('package_add_lesson_cancel'), IsAdmin())
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
        package = await crud.get_lesson_package(session, package_id)
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

    if not package_id:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    raw_text = (message.text or '').strip()
    try:
        local_dt = datetime.strptime(raw_text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(texts.PACKAGE_LESSON_INVALID_DATETIME)
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    tz = ZoneInfo(package.timezone or 'Europe/Moscow')
    local_dt = local_dt.replace(tzinfo=tz)
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

    if not package_id or not scheduled_at_iso:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    duration_text = (message.text or '').strip()
    if duration_text in {'', '-'}:
        duration = None
    else:
        if not duration_text.isdigit() or int(duration_text) <= 0:
            await message.answer(texts.PACKAGE_LESSON_INVALID_DURATION)
            return
        duration = int(duration_text)

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    scheduled_at = datetime.fromisoformat(scheduled_at_iso)

    existing = await crud.fetch_lessons_for_package(session, package_id)
    existing_indices = [lesson.sequence_index for lesson in existing if lesson.sequence_index is not None]
    if existing_indices:
        sequence_index = max(existing_indices) + 1
    else:
        sequence_index = len(existing) + 1

    try:
        await crud.create_lesson(
            session,
            package,
            scheduled_at=scheduled_at,
            sequence_index=sequence_index,
            duration_minutes=duration,
        )
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to add lesson to package %s: %s", package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    package = await crud.get_lesson_package(session, package_id)
    detail_text = _format_package_details(package)
    detail_markup = _build_package_details_keyboard(package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
    await message.answer(texts.PACKAGE_LESSON_CREATED.format(title=escape_html_text(package.title)))
    await state.clear()


@router.callback_query(F.data.startswith('package_lesson_edit'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
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
    await query.message.edit_text(
        texts.PACKAGE_LESSON_EDIT_PROMPT.format(index=lesson_index),
        reply_markup=markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_status'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
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

    markup = _package_lesson_edit_cancel_keyboard(package_id, page).as_markup()
    await query.message.edit_text(
        texts.PACKAGE_LESSON_PROMPT_STATUS.format(index=lesson_index),
        reply_markup=markup,
    )
    await query.answer()


@router.callback_query(F.data.startswith('package_lesson_notes'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
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


@router.callback_query(F.data.startswith('package_lesson_duration'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
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


@router.callback_query(F.data.startswith('package_lesson_delete_confirm'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
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


@router.callback_query(F.data.startswith('package_lesson_delete'), IsAdmin())
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

    lesson = await crud.get_lesson(session, lesson_id)
    if not lesson or lesson.package_id != package_id:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    try:
        await crud.delete_lesson(session, lesson)
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to delete lesson %s from package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for l in lessons:
        l.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer(texts.PACKAGE_LESSON_DELETED.format(index=lesson_index))


@router.callback_query(F.data.startswith('package_lesson_edit_cancel'), IsAdmin())
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
    await state.clear()

    if package_id:
        lessons = await crud.fetch_lessons_for_package(session, package_id)
        package = await crud.get_lesson_package(session, package_id)
        if package:
            for l in lessons:
                l.package = package
            text = _format_lessons_list(lessons)
            markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
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

    if not package_id or not lesson_id:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    raw_text = (message.text or '').strip()
    try:
        local_dt = datetime.strptime(raw_text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer(texts.PACKAGE_LESSON_INVALID_DATETIME)
        return

    package = await crud.get_lesson_package(session, package_id)
    lesson = await crud.get_lesson(session, lesson_id)
    if not package or not lesson:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    tz = ZoneInfo(package.timezone or 'Europe/Moscow')
    scheduled_at = local_dt.replace(tzinfo=tz).astimezone(timezone.utc)

    try:
        lesson.scheduled_at = scheduled_at
        await session.flush([lesson])
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for l in lessons:
        l.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await message.answer(texts.PACKAGE_LESSON_UPDATED.format(index=lesson_index))
    await state.clear()


@router.message(LessonStatusStates.value, F.text, IsAdmin())
async def state_package_lesson_status(message: types.Message, state: FSMContext, session: AsyncSession):
    status = (message.text or '').strip().lower()
    if status not in {'scheduled', 'completed', 'cancelled'}:
        await message.answer(texts.PACKAGE_LESSON_INVALID_STATUS)
        return

    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    if not package_id or not lesson_id:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    package = await crud.get_lesson_package(session, package_id)
    lesson = await crud.get_lesson(session, lesson_id)
    if not package or not lesson:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    try:
        lesson.status = status
        await session.flush([lesson])
        await regenerate_package_reminders(session, package)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson status %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for l in lessons:
        l.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await message.answer(texts.PACKAGE_LESSON_STATUS_UPDATED.format(index=lesson_index))
    await state.clear()


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

    if not package_id or not lesson_id:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    package = await crud.get_lesson_package(session, package_id)
    lesson = await crud.get_lesson(session, lesson_id)
    if not package or not lesson:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    try:
        lesson.teacher_notes = notes
        await session.flush([lesson])
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson notes %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for l in lessons:
        l.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await message.answer(texts.PACKAGE_LESSON_NOTES_UPDATED.format(index=lesson_index))
    await state.clear()


@router.message(LessonDurationStates.value, F.text, IsAdmin())
async def state_package_lesson_duration(message: types.Message, state: FSMContext, session: AsyncSession):
    duration_text = (message.text or '').strip()
    if duration_text in {'', '-'}:
        duration = None
    else:
        if not duration_text.isdigit() or int(duration_text) <= 0:
            await message.answer(texts.PACKAGE_LESSON_INVALID_DURATION)
            return
        duration = int(duration_text)

    data = await state.get_data()
    package_id = data.get('package_id')
    lesson_id = data.get('lesson_id')
    lesson_index = data.get('lesson_index', 1)
    page = int(data.get('list_page', 1))
    menu_chat_id = data.get('menu_chat_id', message.chat.id)
    menu_message_id = data.get('menu_message_id', message.message_id)

    if not package_id or not lesson_id:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    package = await crud.get_lesson_package(session, package_id)
    lesson = await crud.get_lesson(session, lesson_id)
    if not package or not lesson:
        await state.clear()
        await message.answer(texts.PACKAGE_NOT_FOUND)
        return

    try:
        lesson.duration_minutes = duration
        await session.flush([lesson])
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to update lesson duration %s in package %s: %s", lesson_id, package_id, exc, exc_info=True)
        await message.answer(texts.DATABASE_ERROR)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for l in lessons:
        l.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await _safe_edit_message(message.bot, menu_chat_id, menu_message_id, text, markup)
    await message.answer(texts.PACKAGE_LESSON_DURATION_UPDATED.format(index=lesson_index))
    await state.clear()
@router.callback_query(F.data.startswith('package_regenerate'), IsAdmin())
async def cb_package_regenerate(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    try:
        await regenerate_package_reminders(session, package)
        await session.commit()
        await query.answer(texts.PACKAGE_REGENERATED.format(title=escape_html_text(package.title)))
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to regenerate reminders for package %s: %s", package_id, exc, exc_info=True)
        await query.answer(texts.PACKAGE_REGENERATE_FAILED.format(error=escape_html_text(str(exc))), show_alert=True)
        return

    # Refresh package details after regeneration
    package = await crud.get_lesson_package(session, package_id)
    text = _format_package_details(package)
    markup = _build_package_details_keyboard(package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith('package_lessons'), IsAdmin())
async def cb_package_lessons(query: CallbackQuery, session: AsyncSession):
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    package = await crud.get_lesson_package(session, package_id)
    if not package:
        await query.answer(texts.PACKAGE_NOT_FOUND, show_alert=True)
        return

    lessons = await crud.fetch_lessons_for_package(session, package_id)
    for lesson in lessons:
        lesson.package = package

    text = _format_lessons_list(lessons)
    markup = _build_lessons_keyboard(lessons, package_id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()
