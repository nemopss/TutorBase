import logging
import csv
from io import StringIO, BytesIO
import pandas as pd

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database import db
from filters.admin import IsAdmin
from keyboards.common import admin_keyboard
from utils import texts

router = Router()


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


@router.message(Command("admin"))
async def cmd_admin_denied(message: types.Message):
    logging.warning(f"Unauthorized access attempt to /admin by user {message.from_user.id}.")
    await message.answer(texts.ACCESS_DENIED)


@router.callback_query(F.data == 'admin_list', IsAdmin())
async def cb_admin_list(query: CallbackQuery):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested application list.")
    try:
        rows = await db.fetch_last_n(10)
    except Exception as e:
        logging.error(f"Database error in cb_admin_list: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    if not rows:
        await query.message.answer(texts.NO_APPLICATIONS)
        await query.answer()
        return
    response_texts = []
    for r in rows:
        response_texts.append(f"#{r['id']} — {r['created_at']} — {r['name']} ({r['language']}, {r['level']})\nКонтакт: {r['contact']}")
    await query.message.answer('\n\n'.join(response_texts))
    await query.answer()


@router.callback_query(F.data == 'admin_stats', IsAdmin())
async def cb_admin_stats(query: CallbackQuery):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested stats.")
    try:
        cnt = await db.fetch_count()
    except Exception as e:
        logging.error(f"Database error in cb_admin_stats: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return
    await query.message.answer(texts.STATS_TOTAL_APPLICATIONS.format(count=cnt))
    await query.answer()


@router.callback_query(F.data == 'admin_export_csv', IsAdmin())
async def cb_admin_export(query: CallbackQuery):
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested CSV export.")
    try:
        rows = await db.fetch_last_n(10000)
    except Exception as e:
        logging.error(f"Database error in cb_admin_export: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    if not rows:
        await query.message.answer(texts.NO_DATA_TO_EXPORT)
        await query.answer()
        return

    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(['id', 'created_at', 'name', 'language', 'level', 'preferred_time', 'contact'])
    for r in rows:
        writer.writerow([r['id'], r['created_at'], r['name'], r['language'], r['level'], r['preferred_time'], r['contact']])

    csv_bytes = sio.getvalue().encode('utf-8')
    sio.close()

    document = BufferedInputFile(file=csv_bytes, filename='applications.csv')

    await query.message.answer_document(document)
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
async def state_add_student_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    name = user_data.get("name")
    story = user_data.get("story")
    photo_file_id = message.photo[-1].file_id

    try:
        await db.add_student(name, story, photo_file_id)
    except Exception as e:
        logging.error(f"Database error in state_add_student_photo: {e}")
        await message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    await state.clear()
    await message.answer(texts.STUDENT_ADDED_SUCCESS.format(name=name), reply_markup=admin_keyboard())

    admin_user = message.from_user
    log_caption = (
        f"#new_student\n"
        f"👨‍💻 Admin: @{admin_user.username} (ID: {admin_user.id})\n"
        f"✅ Added new student:\n"
        f"👤 Name: {name}\n"
        f"📖 Story: {story[:200]}"
    )
    try:
        await message.bot.send_photo(config.LOGS_CHAT_ID, photo=photo_file_id, caption=log_caption)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")


@router.callback_query(F.data == 'skip_add_photo', AddStudentStates.photo, IsAdmin())
async def cb_skip_add_student_photo(query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    name = user_data.get("name")
    story = user_data.get("story")

    try:
        await db.add_student(name, story, None)
    except Exception as e:
        logging.error(f"Database error in cb_skip_add_student_photo: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await state.clear()
        return

    await state.clear()
    await query.message.edit_text(texts.STUDENT_ADDED_SUCCESS.format(name=name), reply_markup=admin_keyboard())

    admin_user = query.from_user
    log_text = (
        f"#new_student\n"
        f"👨‍💻 Admin: @{admin_user.username} (ID: {admin_user.id})\n"
        f"✅ Added new student:\n"
        f"👤 Name: {name}\n"
        f"📖 Story: {story[:200]}\n"
        f"🖼 Photo: No"
    )
    try:
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as e:
        logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")


@router.callback_query(F.data == 'delete_student', IsAdmin())
async def cb_delete_student_list(query: CallbackQuery):
    try:
        students = await db.get_all_students()
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
            builder.button(text=f"❌ {student['name']}", callback_data=f"delete_confirm_{student['id']}")
        builder.adjust(1)

    builder.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="back_to_admin_panel"))

    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()


@router.callback_query(F.data.startswith("delete_confirm_"), IsAdmin())
async def cb_delete_confirm(query: CallbackQuery):
    student_id = int(query.data.split("_")[2])
    try:
        student = await db.get_student(student_id)
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
        texts.CONFIRM_DELETE_STUDENT.format(name=student['name']),
        reply_markup=builder.as_markup()
    )
    await query.answer()


@router.callback_query(F.data.startswith("delete_execute_"), IsAdmin())
async def cb_delete_execute(query: CallbackQuery):
    student_id = int(query.data.split("_")[2])

    try:
        student = await db.get_student(student_id)
        if not student:
            await query.answer(texts.STUDENT_NOT_FOUND, show_alert=True)
            return

        await db.delete_student(student_id)

        admin_user = query.from_user
        log_text = (
            f"#delete_student\n"
            f"👨‍💻 Admin: @{admin_user.username} (ID: {admin_user.id})\n"
            f"❌ Deleted student:\n"
            f"👤 Name: {student['name']}"
        )
        try:
            await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
        except Exception as e:
            logging.error(f"Failed to send log message to LOGS_CHAT_ID: {e}")

    except Exception as e:
        logging.error(f"Database error in cb_delete_execute: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    await query.message.edit_text(texts.STUDENT_DELETED_SUCCESS, reply_markup=admin_keyboard())
    await query.answer("Удалено!")


@router.callback_query(F.data == 'clear_applications', IsAdmin())
async def cb_clear_applications(query: CallbackQuery):
    try:
        applications = await db.fetch_all_applications()
    except Exception as e:
        logging.error(f"Database error in cb_clear_applications: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    if not applications:
        await query.answer(texts.NO_APPLICATIONS_TO_CLEAR, show_alert=True)
        return

    df = pd.DataFrame(applications)
    
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
    builder.button(text="Отмена", callback_data="back_to_admin_panel")
    await query.message.answer(texts.CLEAR_APPLICATIONS_CONFIRMATION, reply_markup=builder.as_markup())
    await query.answer()


@router.callback_query(F.data == 'confirm_clear_applications', IsAdmin())
async def cb_confirm_clear_applications(query: CallbackQuery):
    try:
        await db.delete_all_applications()
    except Exception as e:
        logging.error(f"Database error in cb_confirm_clear_applications: {e}")
        await query.message.answer(texts.DATABASE_ERROR)
        await query.answer()
        return

    await query.message.edit_text(texts.APPLICATIONS_CLEARED)

    admin_user = query.from_user
    log_text = (
        f"#clear_applications\n"
        f"👨‍💻 Admin: @{admin_user.username} (ID: {admin_user.id})\n"
        f"🗑️ Cleared all applications."
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
    text_to_send = f"{texts.CUTE_MESSAGE_HEADER}\n\n{message.text}"

    for admin_id in config.ADMINS:
        if admin_id != sender_id:
            try:
                await message.bot.send_message(admin_id, text_to_send)
            except Exception as e:
                logging.error(f"Failed to send cute message to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(texts.CUTE_MESSAGE_SENT, reply_markup=admin_keyboard())
