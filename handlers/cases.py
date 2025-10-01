import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud
from utils import texts
from utils.formatters import escape_html_text

router = Router()

# Этот обработчик показывает список всех учеников
@router.callback_query(F.data == "show_cases")
async def cb_show_cases(query: CallbackQuery, session: AsyncSession):
    try:
        students = await crud.get_all_students(session)
    except Exception as exc:
        logging.error(f"Database error while fetching students list: {exc}")
        await query.message.answer(texts.DATABASE_ERROR)
        return

    builder = InlineKeyboardBuilder()
    text = texts.NO_CASES_YET

    if students:
        text = texts.CASES_LIST_HEADER
        for student in students:
            builder.button(text=student.name, callback_data=f"case_{student.id}")
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
async def cb_show_one_case(query: CallbackQuery, session: AsyncSession):
    student_id = int(query.data.split("_")[1])
    try:
        student = await crud.get_student(session, student_id)
    except Exception as exc:
        logging.error(f"Database error while fetching student {student_id}: {exc}")
        await query.message.answer(texts.DATABASE_ERROR)
        return

    if not student:
        await query.answer(texts.STUDENT_NOT_FOUND, show_alert=True)
        return

    text = texts.CASE_STORY_HEADER.format(
        name=escape_html_text(student.name),
        story=escape_html_text(student.story, default=texts.LEARNER_NOTES_EMPTY),
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к списку", callback_data="show_cases")
    builder.button(text="🏠 В меню", callback_data="to_menu")
    builder.adjust(1)

    if student.photo_file_id:
        await query.message.delete() # Удаляем старое сообщение со списком
        await query.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=student.photo_file_id,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await query.message.edit_text(text, reply_markup=builder.as_markup())
    
    await query.answer()
