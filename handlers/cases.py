from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database.db as db
from utils import texts

router = Router()

# Этот обработчик показывает список всех учеников
@router.callback_query(F.data == "show_cases")
async def cb_show_cases(query: CallbackQuery):
    students = await db.get_all_students()

    builder = InlineKeyboardBuilder()
    text = texts.NO_CASES_YET

    if students:
        text = texts.CASES_LIST_HEADER
        for student in students:
            builder.button(text=student['name'], callback_data=f"case_{student['id']}")
        builder.adjust(2) # Расположим по 2 кнопки в ряд

    # Добавляем кнопку "В меню"
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_menu"))

    try:
        await query.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await query.message.delete()
        await query.message.answer(text, reply_markup=builder.as_markup())
    finally:
        await query.answer()


# Этот обработчик показывает историю конкретного ученика
@router.callback_query(F.data.startswith("case_"))
async def cb_show_one_case(query: CallbackQuery):
    student_id = int(query.data.split("_")[1])
    student = await db.get_student(student_id)

    if not student:
        await query.answer(texts.STUDENT_NOT_FOUND, show_alert=True)
        return

    text = texts.CASE_STORY_HEADER.format(name=student['name'], story=student['story'])

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к списку", callback_data="show_cases")
    builder.button(text="🏠 В меню", callback_data="to_menu")
    builder.adjust(1)

    if student.get('photo_file_id'):
        await query.message.delete() # Удаляем старое сообщение со списком
        await query.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=student['photo_file_id'],
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await query.message.edit_text(text, reply_markup=builder.as_markup())
    
    await query.answer()
