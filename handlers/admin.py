import logging

from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db
from filters.admin import IsAdmin
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardButton
from keyboards.common import admin_keyboard
from database.db import fetch_last_n, fetch_count
from config import config
import csv
from io import StringIO

router = Router()

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: types.Message):
    logging.info(f"Admin {message.from_user.id} accessed admin panel.")
    await message.answer('Панель администратора:', reply_markup=admin_keyboard())

@router.message(Command("admin"))
async def cmd_admin_denied(message: types.Message):
    logging.warning(f"Unauthorized access attempt to /admin by user {message.from_user.id}.")
    await message.answer('Доступ запрещён.')


@router.callback_query(F.data == 'admin_list')
async def cb_admin_list(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested application list.")
    rows = await fetch_last_n(10)
    if not rows:
        await query.message.answer('Заявок пока нет.')
        await query.answer()
        return
    texts = []
    for r in rows:
        texts.append(f"#{r['id']} — {r['created_at']} — {r['name']} ({r['language']}, {r['level']})\nКонтакт: {r['contact']}")
    await query.message.answer('\n\n'.join(texts))
    await query.answer()

@router.callback_query(F.data == 'admin_stats')
async def cb_admin_stats(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested stats.")
    cnt = await fetch_count()
    await query.message.answer(f'Всего заявок: {cnt}')
    await query.answer()

@router.callback_query(F.data == 'admin_export_csv')
async def cb_admin_export(query: CallbackQuery):
    if query.from_user.id not in config.ADMINS:
        await query.answer('Доступ запрещён', show_alert=True)
        return
    logging.info(f"Admin {query.from_user.id} (@{query.from_user.username}) requested CSV export.")
    rows = await fetch_last_n(10000)
    if not rows:
        await query.message.answer('Нет данных для экспорта.')
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

class AddStudentStates(StatesGroup):
    name = State()
    story = State()


@router.callback_query(F.data == 'add_student', IsAdmin())
async def cb_add_student(query: CallbackQuery, state: FSMContext):
    await state.set_state(AddStudentStates.name)
    await query.message.edit_text("Введите имя ученика (оно будет на кнопке):")
    await query.answer()

# Шаг 2: Админ вводит имя, бот просит историю
@router.message(AddStudentStates.name, F.text, IsAdmin())
async def state_add_student_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddStudentStates.story)
    await message.answer("Теперь введите историю успеха ученика (можно длинным текстом):")

# Шаг 3: Админ вводит историю, бот сохраняет в БД
@router.message(AddStudentStates.story, F.text, IsAdmin())
async def state_add_student_story(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    name = user_data.get("name")
    story = message.text.strip()

    await db.add_student(name, story) # Используем нашу функцию из db.py

    await state.clear()
    await message.answer(f"Ученик '{name}' успешно добавлен!", reply_markup=admin_keyboard())


# --- Логика для удаления ученика ---

# Шаг 1: Показываем список учеников для удаления
@router.callback_query(F.data == 'delete_student', IsAdmin())
async def cb_delete_student_list(query: CallbackQuery):
    students = await db.get_all_students()

    builder = InlineKeyboardBuilder()
    text = "В базе пока нет учеников."

    if students:
        text = "Выберите ученика, которого хотите удалить:"
        for student in students:
            # Добавляем эмодзи для наглядности
            builder.button(text=f"❌ {student['name']}", callback_data=f"delete_confirm_{student['id']}")
        builder.adjust(1)

    # Кнопка для возврата в главное меню админки
    builder.row(InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="back_to_admin_panel"))

    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()


# Шаг 2: Просим подтверждение на удаление
@router.callback_query(F.data.startswith("delete_confirm_"), IsAdmin())
async def cb_delete_confirm(query: CallbackQuery):
    # query.data будет в формате "delete_confirm_123"
    student_id = int(query.data.split("_")[2])
    student = await db.get_student(student_id)

    if not student:
        await query.answer("Ученик не найден!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=f"delete_execute_{student_id}")
    builder.button(text="Нет, назад к списку", callback_data="delete_student")
    builder.adjust(1)

    await query.message.edit_text(
        f"Вы уверены, что хотите удалить ученика '{student['name']}'? Это действие необратимо.",
        reply_markup=builder.as_markup()
    )
    await query.answer()


# Шаг 3: Окончательное удаление
@router.callback_query(F.data.startswith("delete_execute_"), IsAdmin())
async def cb_delete_execute(query: CallbackQuery):
    student_id = int(query.data.split("_")[2])

    await db.delete_student(student_id)

    await query.message.edit_text("Ученик успешно удален.", reply_markup=admin_keyboard())
    await query.answer("Удалено!")


# Обработчик для кнопки "Назад в админ-панель"
@router.callback_query(F.data == 'back_to_admin_panel', IsAdmin())
async def cb_back_to_admin_panel(query: CallbackQuery):
    await query.message.edit_text('Панель администратора:', reply_markup=admin_keyboard())
    await query.answer()
