import logging
import csv
import math
from datetime import datetime, timezone, timedelta
from io import StringIO, BytesIO
from typing import NamedTuple
import pandas as pd

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from config import config
from database import crud
from database.models import Application, BotUser
from utils.state import get_bot_started_at
from filters.admin import IsAdmin
from keyboards.common import (
    admin_keyboard,
    admin_stats_keyboard,
    admin_cases_keyboard,
)
from utils import texts
from utils.formatters import (
    escape_html_text,
    format_timestamp_msk,
    pack_chat_identifier,
    split_chat_identifier,
    format_applications_stats,
)

router = Router()
DAY_LABELS = [
    (0, "Пн"),
    (1, "Вт"),
    (2, "Ср"),
    (3, "Чт"),
    (4, "Пт"),
    (5, "Сб"),
    (6, "Вс"),
]

LEARNERS_PER_PAGE = 5
BOT_USERS_PER_PAGE = 6



class ContactPayload(NamedTuple):
    value: str
    requires_resolution: bool
    display: str


class LearnerCreateStates(StatesGroup):
    selecting_user = State()
    display_name = State()
    notes = State()


def _contact_to_payload(raw: str) -> ContactPayload:
    value = raw.strip()
    if not value:
        raise ValueError("empty contact")
    if value.startswith("tg://user?id="):
        _, _, identifier = value.partition("=")
        identifier = identifier.strip()
        if identifier.lstrip("-").isdigit():
            return ContactPayload(identifier, False, identifier)
        raise ValueError("invalid contact")
    if value.startswith(("https://t.me/", "http://t.me/")):
        username = value.rsplit("/", 1)[-1].strip()
        if username.startswith("@"):
            username = username[1:]
        if not username:
            raise ValueError("invalid contact")
        return ContactPayload(username, True, f"@{username}")
    if value.startswith("@"):
        username = value[1:].strip()
        if not username:
            raise ValueError("invalid contact")
        return ContactPayload(username, True, f"@{username}")
    if value.lstrip("-").isdigit():
        return ContactPayload(value, False, value)
    raise ValueError("invalid contact")


def _calc_total_pages(total: int, per_page: int) -> int:
    if total <= 0:
        return 1
    return max(1, math.ceil(total / per_page))


def _format_username(bot_user) -> str:
    if not bot_user or not bot_user.username:
        return "—"
    return f"@{bot_user.username}"


def _format_bot_user_display(bot_user) -> str:
    if not bot_user:
        return "—"
    parts = [part for part in [bot_user.first_name, bot_user.last_name] if part]
    if parts:
        return " ".join(parts)
    if bot_user.username:
        return f"@{bot_user.username}"
    return str(bot_user.chat_id)


def _add_pagination(builder: InlineKeyboardBuilder, page: int, total_pages: int, prefix: str) -> None:
    if total_pages <= 1:
        return
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text='⬅️', callback_data=f'{prefix}:{page - 1}'))
    buttons.append(InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text='➡️', callback_data=f'{prefix}:{page + 1}'))
    builder.row(*buttons)


def _format_learners_menu_text(learners, page: int, total_pages: int, total_count: int) -> str:
    if not learners:
        return texts.LEARNERS_EMPTY

    start_index = (page - 1) * LEARNERS_PER_PAGE + 1
    lines = [texts.LEARNERS_MENU_HEADER.format(total=total_count), ""]
    for idx, learner in enumerate(learners, start=start_index):
        username = _format_username(learner.bot_user)
        lines.append(
            texts.LEARNERS_MENU_ITEM.format(
                index=idx,
                name=escape_html_text(learner.display_name),
                username=escape_html_text(username or "—"),
            )
        )
    lines.extend(["", texts.LEARNERS_MENU_FOOTER.format(page=page, pages=total_pages)])
    return "\n".join(lines)


def _build_learners_keyboard(learners, page: int, total_pages: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for learner in learners:
        builder.button(
            text=f"👤 {learner.display_name}",
            callback_data=f"learner_view:{learner.id}:{page}"
        )
    if learners:
        builder.adjust(1)
    _add_pagination(builder, page, total_pages, 'learners_page')
    builder.row(InlineKeyboardButton(text='➕ Добавить ученика', callback_data=f'learner_add:{page}'))
    builder.row(InlineKeyboardButton(text='💌 Сообщение!', callback_data='send_cute_message'))
    builder.row(InlineKeyboardButton(text='⬅️ Назад', callback_data='back_to_admin_panel'))
    return builder


def _build_bot_user_picker_keyboard(users, page: int, total_pages: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for user in users:
        label = _format_bot_user_display(user)
        username = _format_username(user)
        if username != '—':
            label = f"{label} ({username})"
        builder.button(
            text=label[:60],
            callback_data=f"learner_select:{user.id}:{page}"
        )
    if users:
        builder.adjust(1)
    _add_pagination(builder, page, total_pages, 'learner_users_page')
    builder.row(InlineKeyboardButton(text='⬅️ Отмена', callback_data='learner_add_cancel'))
    return builder


def _format_learner_detail_text(learner) -> str:
    username = escape_html_text(_format_username(learner.bot_user) or '—')
    chat_id = escape_html_text(learner.bot_user.chat_id if learner.bot_user else '—')
    last_seen = escape_html_text(
        format_timestamp_msk(learner.bot_user.last_seen_at) if learner.bot_user else '—'
    )
    notes = escape_html_text(learner.notes or texts.LEARNER_NOTES_EMPTY, default=texts.LEARNER_NOTES_EMPTY)
    created = escape_html_text(format_timestamp_msk(learner.created_at))
    return texts.LEARNER_DETAILS.format(
        name=escape_html_text(learner.display_name),
        username=username,
        chat_id=chat_id,
        last_seen=last_seen,
        created_at=created,
        notes=notes,
    )


def _build_learner_detail_keyboard(learner_id: int, page: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text='🗑 Удалить', callback_data=f'learner_delete_confirm:{learner_id}:{page}')
    builder.button(text='⬅️ Назад', callback_data=f'learners_page:{page}')
    builder.adjust(1)
    return builder


async def _prepare_learners_menu(session: AsyncSession, page: int):
    per_page = LEARNERS_PER_PAGE
    offset = max(0, (page - 1) * per_page)
    learners, total = await crud.fetch_learners_paginated(session, limit=per_page, offset=offset)

    total_pages = _calc_total_pages(total, per_page)
    if page > total_pages and total > 0:
        page = total_pages
        offset = max(0, (page - 1) * per_page)
        learners, total = await crud.fetch_learners_paginated(session, limit=per_page, offset=offset)

    text = _format_learners_menu_text(learners, page, total_pages, total)
    markup = _build_learners_keyboard(learners, page, total_pages).as_markup()
    return page, text, markup


async def _show_learners_menu(message: types.Message, session: AsyncSession, page: int) -> int:
    page, text, markup = await _prepare_learners_menu(session, page)
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=markup)
    return page


async def _edit_menu_message(bot, chat_id: int, message_id: int, text: str, markup) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    except TelegramBadRequest as exc:
        # Telegram returns "message is not modified" when the target message already contains
        # the same text. In this case we can safely ignore the error instead of duplicating
        # the menu with a fresh message.
        if "message is not modified" in str(exc).lower():
            return
        await bot.send_message(chat_id, text, reply_markup=markup)


async def _show_bot_user_picker(
    message: types.Message,
    session: AsyncSession,
    page: int,
    return_page: int,
) -> tuple[int, int]:
    per_page = BOT_USERS_PER_PAGE
    offset = max(0, (page - 1) * per_page)
    users, total = await crud.fetch_available_bot_users(session, limit=per_page, offset=offset)
    total_pages = _calc_total_pages(total, per_page)
    if page > total_pages and total > 0:
        page = total_pages
        offset = max(0, (page - 1) * per_page)
        users, total = await crud.fetch_available_bot_users(session, limit=per_page, offset=offset)

    if not users:
        builder = InlineKeyboardBuilder()
        builder.button(text='⬅️ Назад', callback_data=f'learners_page:{return_page}')
        try:
            await message.edit_text(texts.LEARNER_NO_AVAILABLE_USERS, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            await message.answer(texts.LEARNER_NO_AVAILABLE_USERS, reply_markup=builder.as_markup())
        return page, total_pages

    text = texts.LEARNER_PICK_USER.format(page=page, pages=total_pages)
    markup = _build_bot_user_picker_keyboard(users, page, total_pages).as_markup()
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=markup)
    return page, total_pages



class AddStudentStates(StatesGroup):
    name = State()
    story = State()
    photo = State()

class CuteMessageStates(StatesGroup):
    message = State()



@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: types.Message):
    logging.info(f"Admin {message.from_user.id} accessed admin panel.")
    await message.answer(texts.ADMIN_PANEL, reply_markup=admin_keyboard())


@router.message(Command("status"), IsAdmin())
async def cmd_status(message: types.Message, session: AsyncSession):
    logging.info("Admin %s requested status", message.from_user.id)

    bot_started_at = get_bot_started_at()
    started_at_text = "—"
    if isinstance(bot_started_at, datetime):
        started_at_text = escape_html_text(format_timestamp_msk(bot_started_at))

    now_utc = datetime.now(timezone.utc)
    week_ago = now_utc - timedelta(days=7)

    pending_instances = await crud.fetch_reminder_instances_count(session, status='scheduled')
    total_instances = await crud.fetch_reminder_instances_count(session)
    active_reminders = pending_instances
    total_reminders = total_instances

    recent_applications = (
        await session.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.created_at >= week_ago)
        )
    ).scalar_one()

    total_users = (
        await session.execute(select(func.count()).select_from(BotUser))
    ).scalar_one()

    text = texts.STATUS_REPORT.format(
        started_at=started_at_text,
        active_reminders=escape_html_text(active_reminders),
        total_reminders=escape_html_text(total_reminders),
        recent_applications=escape_html_text(recent_applications),
        total_users=escape_html_text(total_users),
    )

    await message.answer(text, reply_markup=admin_keyboard())


@router.callback_query(F.data == 'admin_stats_menu', IsAdmin())
async def cb_admin_stats_menu(query: CallbackQuery):
    logging.info(f"Admin {query.from_user.id} opened stats menu.")
    await query.message.edit_text(texts.ADMIN_STATS_MENU, reply_markup=admin_stats_keyboard())
    await query.answer()


@router.callback_query(F.data == 'cases_manager', IsAdmin())
async def cb_cases_manager(query: CallbackQuery, state: FSMContext):
    logging.info(f"Admin {query.from_user.id} opened cases manager.")
    await state.clear()
    await query.message.edit_text(texts.ADMIN_CASES_MENU, reply_markup=admin_cases_keyboard())
    await query.answer()


@router.message(Command("admin"))
async def cmd_admin_denied(message: types.Message):
    logging.warning(f"Unauthorized access attempt to /admin by user {message.from_user.id}.")
    await message.answer(texts.ACCESS_DENIED)




@router.callback_query(F.data == 'admin_list', IsAdmin())
async def cb_admin_list(query: CallbackQuery, session: AsyncSession):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested application list.")
    try:
        rows = await crud.fetch_last_n_applications(session, 10)
    except Exception as e:
        logging.error(f"Database error in cb_admin_list: {e}")
        await query.message.edit_text(texts.DATABASE_ERROR, reply_markup=admin_stats_keyboard())
        await query.answer()
        return

    if not rows:
        await query.message.edit_text(texts.NO_APPLICATIONS, reply_markup=admin_stats_keyboard())
        await query.answer()
        return
    response_texts = []
    for r in rows:
        created_at = escape_html_text(format_timestamp_msk(r.created_at))
        response_texts.append(
            f"#{escape_html_text(r.id)} — {created_at} — {escape_html_text(r.name)}"
            f" ({escape_html_text(r.language)}, {escape_html_text(r.level)})\n"
            f"Контакт: {escape_html_text(r.contact)}"
        )
    await query.message.edit_text('\n\n'.join(response_texts), reply_markup=admin_stats_keyboard())
    await query.answer()


@router.callback_query(F.data == 'admin_stats', IsAdmin())
async def cb_admin_stats(query: CallbackQuery, session: AsyncSession):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested stats.")
    try:
        stats = await crud.fetch_applications_stats(session)
    except Exception as e:
        logging.error(f"Database error in cb_admin_stats: {e}")
        await query.message.edit_text(texts.DATABASE_ERROR, reply_markup=admin_stats_keyboard())
        await query.answer()
        return
    stats_text = format_applications_stats(stats)
    display_text = f"{texts.ADMIN_STATS_MENU}\n\n{stats_text}"
    await query.message.edit_text(display_text, reply_markup=admin_stats_keyboard())
    await query.answer()


@router.callback_query(F.data == 'admin_export_csv', IsAdmin())
async def cb_admin_export(query: CallbackQuery, session: AsyncSession):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested CSV export.")
    try:
        rows = await crud.fetch_all_applications(session)
    except Exception as e:
        logging.error(f"Database error in cb_admin_export: {e}")
        await query.message.edit_text(texts.DATABASE_ERROR, reply_markup=admin_stats_keyboard())
        await query.answer()
        return

    if not rows:
        await query.message.edit_text(texts.NO_DATA_TO_EXPORT, reply_markup=admin_stats_keyboard())
        await query.answer()
        return

    data = [{"id": r.id, "created_at": r.created_at, "name": r.name, "language": r.language, "level": r.level, "preferred_time": r.preferred_time, "contact": r.contact} for r in rows]
    df = pd.DataFrame(data)
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    csv_document = BufferedInputFile(file=csv_buffer.getvalue().encode('utf-8'), filename='applications.csv')

    await query.message.answer_document(csv_document)
    await query.message.edit_text(texts.ADMIN_STATS_MENU, reply_markup=admin_stats_keyboard())
    await query.answer()


@router.callback_query(F.data == 'add_student', IsAdmin())
async def cb_add_student(query: CallbackQuery, state: FSMContext):
    await state.set_state(AddStudentStates.name)
    await query.message.edit_text(texts.PROMPT_ADD_STUDENT_NAME)
    await query.answer()


@router.message(AddStudentStates.name, F.text, IsAdmin())
async def state_add_student_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddStudentStates.story)
    await message.answer(texts.PROMPT_ADD_STUDENT_STORY)


@router.message(AddStudentStates.story, F.text, IsAdmin())
async def state_add_student_story(message: types.Message, state: FSMContext):
    await state.update_data(story=message.text.strip())
    await state.set_state(AddStudentStates.photo)
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="skip_add_photo")
    await message.answer(texts.PROMPT_ADD_STUDENT_PHOTO, reply_markup=builder.as_markup())


@router.message(AddStudentStates.photo, F.photo, IsAdmin())
async def state_add_student_photo(message: types.Message, state: FSMContext, session: AsyncSession):
    user_data = await state.get_data()
    name = user_data.get("name")
    story = user_data.get("story")
    photo_file_id = message.photo[-1].file_id

    try:
        await crud.add_student(session, name, story, photo_file_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logging.error(f"Database error in state_add_student_photo: {e}")
        await message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    await state.clear()
    await message.answer(
        texts.STUDENT_ADDED_SUCCESS.format(name=escape_html_text(name)),
        reply_markup=admin_cases_keyboard(),
    )

    admin_user = message.from_user
    log_caption = (
        "#new_student\n"
        f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
        "✅ Added new student:\n"
        f"👤 Name: {escape_html_text(name)}\n"
        f"📖 Story: {escape_html_text(story[:200])}"
    )
    try:
        await message.bot.send_photo(config.LOGS_CHAT_ID, photo=photo_file_id, caption=log_caption)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")



@router.callback_query(F.data == 'skip_add_photo', AddStudentStates.photo, IsAdmin())
async def cb_skip_add_student_photo(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_data = await state.get_data()
    name = user_data.get("name")
    story = user_data.get("story")

    try:
        await crud.add_student(session, name, story, None)
    except Exception as e:
        logging.error(f"Database error in cb_skip_add_student_photo: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    await state.clear()
    await query.message.edit_text(
        texts.STUDENT_ADDED_SUCCESS.format(name=escape_html_text(name)),
        reply_markup=admin_cases_keyboard(),
    )

    admin_user = query.from_user
    log_text = (
        "#new_student\n"
        f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
        "✅ Added new student:\n"
        f"👤 Name: {escape_html_text(name)}\n"
        f"📖 Story: {escape_html_text(story[:200])}\n"
        "🖼 Photo: No"
    )
    try:
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")


@router.callback_query(F.data == 'delete_student', IsAdmin())
async def cb_delete_student_list(query: CallbackQuery, session: AsyncSession):
    try:
        students = await crud.get_all_students(session)
    except Exception as e:
        logging.error(f"Database error in cb_delete_student_list: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    builder = InlineKeyboardBuilder()
    text = texts.NO_STUDENTS_IN_DB

    if students:
        text = texts.CHOOSE_STUDENT_TO_DELETE
        for student in students:
            builder.button(text=f"❌ {student.name}", callback_data=f"delete_confirm_{student.id}")
        builder.adjust(1)

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="cases_manager"))

    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()


@router.callback_query(F.data.startswith("delete_confirm_"), IsAdmin())
async def cb_delete_confirm(query: CallbackQuery, session: AsyncSession):
    student_id = int(query.data.split("_")[2])
    try:
        student = await crud.get_student(session, student_id)
    except Exception as e:
        logging.error(f"Database error in cb_delete_confirm: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    if not student:
        await query.answer(texts.STUDENT_NOT_FOUND, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=f"delete_execute_{student_id}")
    builder.button(text="Нет, назад к списку", callback_data="delete_student")
    builder.adjust(1)

    await query.message.edit_text(
        texts.CONFIRM_DELETE_STUDENT.format(name=escape_html_text(student.name)),
        reply_markup=builder.as_markup()
    )
    await query.answer()


@router.callback_query(F.data.startswith("delete_execute_"), IsAdmin())
async def cb_delete_execute(query: CallbackQuery, session: AsyncSession):
    student_id = int(query.data.split("_")[2])

    try:
        student = await crud.get_student(session, student_id)
        if not student:
            await query.answer(texts.STUDENT_NOT_FOUND, show_alert=True)
            return

        student_name = student.name
        await crud.delete_student(session, student_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logging.error(f"Database error in cb_delete_execute: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    admin_user = query.from_user
    log_text = (
        "#delete_student\n"
        f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
        "❌ Deleted student:\n"
        f"👤 Name: {escape_html_text(student_name)}"
    )
    try:
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")

    await query.message.edit_text(texts.STUDENT_DELETED_SUCCESS, reply_markup=admin_cases_keyboard())
    await query.answer("Удалено!")


@router.callback_query(F.data == 'clear_applications', IsAdmin())
async def cb_clear_applications(query: CallbackQuery, session: AsyncSession):
    try:
        applications = await crud.fetch_all_applications(session)
    except Exception as e:
        logging.error(f"Database error in cb_clear_applications: {e}")
        await query.message.edit_text(texts.DATABASE_ERROR, reply_markup=admin_stats_keyboard())
        await query.answer()
        return

    if not applications:
        await query.answer(texts.NO_APPLICATIONS_TO_CLEAR, show_alert=True)
        return

    data = [{"id": r.id, "created_at": r.created_at, "name": r.name, "language": r.language, "level": r.level, "preferred_time": r.preferred_time, "contact": r.contact} for r in applications]
    df = pd.DataFrame(data)
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    csv_document = BufferedInputFile(file=csv_buffer.getvalue().encode('utf-8'), filename='applications.csv')

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Applications')
    excel_buffer.seek(0)
    excel_document = BufferedInputFile(file=excel_buffer.read(), filename='applications.xlsx')

    await query.message.answer_document(csv_document)
    await query.message.answer_document(excel_document)

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, очистить", callback_data="confirm_clear_applications")
    builder.button(text="Отмена", callback_data="admin_stats_menu")
    await query.message.answer(texts.CLEAR_APPLICATIONS_CONFIRMATION, reply_markup=builder.as_markup())
    await query.answer()


@router.callback_query(F.data == 'confirm_clear_applications', IsAdmin())
async def cb_confirm_clear_applications(query: CallbackQuery, session: AsyncSession):
    try:
        await crud.delete_all_applications(session)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logging.error(f"Database error in cb_confirm_clear_applications: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    await query.message.edit_text(texts.APPLICATIONS_CLEARED, reply_markup=admin_stats_keyboard())

    admin_user = query.from_user
    log_text = (
        "#clear_applications\n"
        f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
        "🗑️ Cleared all applications."
    )
    try:
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")

    await query.answer()


@router.callback_query(F.data == 'back_to_admin_panel', IsAdmin())
async def cb_back_to_admin_panel(query: CallbackQuery):
    await query.message.edit_text(texts.ADMIN_PANEL, reply_markup=admin_keyboard())
    await query.answer()


@router.callback_query(F.data == 'send_cute_message', IsAdmin())
async def cb_send_cute_message(query: CallbackQuery, state: FSMContext):
    await state.set_state(CuteMessageStates.message)
    await query.message.edit_text(texts.PROMPT_FOR_CUTE_MESSAGE)
    await query.answer()


@router.message(CuteMessageStates.message, F.text, IsAdmin())
async def state_send_cute_message(message: types.Message, state: FSMContext):
    sender_id = message.from_user.id
    text_to_send = (
        f"{texts.CUTE_MESSAGE_HEADER}\n\n"
        f"{escape_html_text(message.text, default='—')}"
    )

    for admin_id in config.ADMINS:
        if admin_id != sender_id:
            try:
                await message.bot.send_message(admin_id, text_to_send)
            except Exception as e:
                logging.error(f"Failed to send cute message to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(texts.CUTE_MESSAGE_SENT, reply_markup=admin_keyboard())


@router.callback_query(F.data == 'manage_students', IsAdmin())
async def cb_manage_students(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await _show_learners_menu(query.message, session, page=1)
    await query.answer()


@router.callback_query(F.data.startswith('learners_page:'), IsAdmin())
async def cb_learners_page(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        page = int(query.data.split(':')[1])
    except (IndexError, ValueError):
        page = 1
    await state.clear()
    await _show_learners_menu(query.message, session, page)
    await query.answer()


@router.callback_query(F.data.startswith('learner_add:'), IsAdmin())
async def cb_learner_add(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = query.data.split(':')
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    await state.set_state(LearnerCreateStates.selecting_user)
    await state.update_data(
        return_page=page,
        menu_chat_id=query.message.chat.id,
        menu_message_id=query.message.message_id,
    )
    await _show_bot_user_picker(query.message, session, page=1, return_page=page)
    await query.answer()


@router.callback_query(F.data.startswith('learner_users_page:'), IsAdmin())
async def cb_learner_users_page(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    current_state = await state.get_state()
    if current_state != LearnerCreateStates.selecting_user.state:
        await query.answer()
        return
    try:
        page = int(query.data.split(':')[1])
    except (IndexError, ValueError):
        page = 1
    await state.update_data(picker_page=page)
    return_page = int((await state.get_data()).get('return_page', 1))
    await _show_bot_user_picker(query.message, session, page, return_page=return_page)
    await query.answer()


@router.callback_query(F.data == 'learner_add_cancel', IsAdmin())
async def cb_learner_add_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    return_page = int(data.get('return_page', 1))
    menu_chat_id = data.get('menu_chat_id')
    menu_message_id = data.get('menu_message_id')
    await state.clear()
    page, text, markup = await _prepare_learners_menu(session, return_page)

    
    if menu_chat_id and menu_message_id:
        await _edit_menu_message(query.message.bot, menu_chat_id, menu_message_id, text, markup)
        if query.message.message_id != menu_message_id:
            try:
                await query.message.delete()
            except TelegramBadRequest:
                pass
    else:
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await query.message.answer(text, reply_markup=markup)

    await query.answer()


@router.callback_query(F.data.startswith('learner_select:'), IsAdmin())
async def cb_learner_select(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    if await state.get_state() != LearnerCreateStates.selecting_user.state:
        await query.answer()
        return
    try:
        _, bot_user_id_str, picker_page_str = query.data.split(':')
        bot_user_id = int(bot_user_id_str)
        picker_page = int(picker_page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    existing = await crud.get_learner_by_bot_user(session, bot_user_id)
    if existing:
        await query.answer(texts.LEARNER_ALREADY_EXISTS, show_alert=True)
        return

    bot_user = await crud.get_bot_user(session, bot_user_id)
    if not bot_user:
        await query.answer(texts.LEARNER_USER_NOT_FOUND, show_alert=True)
        return

    suggested = _format_bot_user_display(bot_user)
    await state.update_data(
        bot_user_id=bot_user_id,
        suggested_name=suggested,
        picker_page=picker_page,
    )
    await state.set_state(LearnerCreateStates.display_name)

    markup = InlineKeyboardBuilder()
    markup.button(text='⬅️ Отмена', callback_data='learner_add_cancel')
    await query.message.edit_text(
        texts.LEARNER_PROMPT_DISPLAY.format(default=escape_html_text(suggested)),
        reply_markup=markup.as_markup()
    )
    await query.answer()


@router.message(LearnerCreateStates.display_name, F.text, IsAdmin())
async def state_learner_display_name(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    data = await state.get_data()
    suggested = data.get('suggested_name') or '—'
    display_name = suggested if text in {'', '-'} else text
    if not display_name:
        await message.answer(
            texts.LEARNER_PROMPT_DISPLAY.format(default=escape_html_text(suggested))
        )
        return
    await state.update_data(display_name=display_name)
    await state.set_state(LearnerCreateStates.notes)
    await message.answer(texts.LEARNER_PROMPT_NOTES)


@router.message(LearnerCreateStates.notes, F.text, IsAdmin())
async def state_learner_notes(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    bot_user_id = data.get('bot_user_id')
    display_name = data.get('display_name')
    return_page = int(data.get('return_page', 1))
    menu_chat_id = data.get('menu_chat_id')
    menu_message_id = data.get('menu_message_id')

    if not bot_user_id or not display_name or not menu_chat_id or not menu_message_id:
        await state.clear()
        await message.answer(texts.LEARNER_INTERNAL_ERROR)
        return

    notes_text = (message.text or '').strip()
    notes = None if notes_text in {'', '-'} else notes_text

    existing = await crud.get_learner_by_bot_user(session, bot_user_id)
    if existing:
        learner = await crud.get_learner(session, existing.id)
        detail_markup = _build_learner_detail_keyboard(existing.id, return_page).as_markup()
        detail_text = _format_learner_detail_text(learner)
        await _edit_menu_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)
        await state.clear()
        await message.answer(texts.LEARNER_ALREADY_EXISTS)
        return

    learner = await crud.create_learner(
        session,
        bot_user_id=bot_user_id,
        display_name=display_name,
        notes=notes,
    )
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to create learner: %s", exc, exc_info=True)
        await state.clear()
        await message.answer(texts.LEARNER_INTERNAL_ERROR)
        return

    learner = await crud.get_learner(session, learner.id)

    detail_markup = _build_learner_detail_keyboard(learner.id, return_page).as_markup()
    detail_text = _format_learner_detail_text(learner)
    await _edit_menu_message(message.bot, menu_chat_id, menu_message_id, detail_text, detail_markup)

    await state.clear()
    await message.answer(
        texts.LEARNER_CREATED.format(name=escape_html_text(learner.display_name))
    )

    try:
        admin_user = message.from_user
        log_text = (
            "#learner_added\n"
            f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
            "➕ Learner: "
            f"{escape_html_text(learner.display_name)} (chat_id: {escape_html_text(learner.bot_user.chat_id)})"
        )
        await message.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as exc:
        logging.error("Failed to send learner added log: %s", exc)


@router.callback_query(F.data.startswith('learner_view:'), IsAdmin())
async def cb_learner_view(query: CallbackQuery, session: AsyncSession):
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
        await _show_learners_menu(query.message, session, page)
        return

    text = _format_learner_detail_text(learner)
    markup = _build_learner_detail_keyboard(learner.id, page).as_markup()
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(F.data.startswith('learner_delete_confirm:'), IsAdmin())
async def cb_learner_delete_confirm(query: CallbackQuery, session: AsyncSession):
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
        await _show_learners_menu(query.message, session, page)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text='🗑 Да, удалить', callback_data=f'learner_delete_execute:{learner.id}:{page}')
    builder.button(text='⬅️ Назад', callback_data=f'learner_view:{learner.id}:{page}')
    builder.adjust(1)

    await query.message.edit_text(
        texts.LEARNER_DELETE_CONFIRM.format(name=escape_html_text(learner.display_name)),
        reply_markup=builder.as_markup()
    )
    await query.answer()


@router.callback_query(F.data.startswith('learner_delete_execute:'), IsAdmin())
async def cb_learner_delete_execute(query: CallbackQuery, session: AsyncSession):
    try:
        _, learner_id_str, page_str = query.data.split(':')
        learner_id = int(learner_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    try:
        learner = await crud.get_learner(session, learner_id)
        if not learner:
            await query.answer(texts.LEARNER_NOT_FOUND, show_alert=True)
            # Try to refresh menu gracefully
            await _show_learners_menu(query.message, session, page)
            return

        await crud.delete_learner(session, learner)
        await session.commit()

        # Log deletion
        try:
            admin_user = query.from_user
            log_text = (
                "#learner_deleted\n"
                f"👨‍💻 Admin: @{escape_html_text(admin_user.username or admin_user.id)} (ID: {admin_user.id})\n"
                "🗑 Learner: "
                f"{escape_html_text(learner.display_name)} (chat_id: {escape_html_text(learner.bot_user.chat_id if learner.bot_user else '—')})"
            )
            await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
        except Exception as exc:
            logging.error("Failed to send learner deleted log: %s", exc)

        await query.answer(texts.LEARNER_DELETED)
        await _show_learners_menu(query.message, session, page)

    except Exception as exc:
        await session.rollback()
        logging.error("Error in cb_learner_delete_execute: %s", exc, exc_info=True)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        # Try to refresh menu gracefully
        await _show_learners_menu(query.message, session, page)


@router.callback_query(F.data == 'noop', IsAdmin())
async def cb_noop(query: CallbackQuery):
    await query.answer()

