from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database.db as db

router = Router()

# Этот обработчик показывает список всех учеников
@router.callback_query(F.data == "show_cases")
async def cb_show_cases(query: CallbackQuery):
    students = await db.get_all_students()

    builder = InlineKeyboardBuilder()
    text = "Пока здесь нет историй учеников."

    if students:
        text = "Вот результаты некоторых моих учеников. Нажмите на имя, чтобы прочитать историю:"
        for student in students:
            builder.button(text=student['name'], callback_data=f"case_{student['id']}")
        builder.adjust(2) # Расположим по 2 кнопки в ряд

    # Добавляем кнопку "В меню"
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_menu"))

    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()


# Этот обработчик показывает историю конкретного ученика
@router.callback_query(F.data.startswith("case_"))
async def cb_show_one_case(query: CallbackQuery):
    student_id = int(query.data.split("_")[1])
    student = await db.get_student(student_id)

    if not student:
        await query.answer("Ученик не найден!", show_alert=True)
        return

    text = f"Кейс: {student['name']}\n\n{student['story']}"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к списку", callback_data="show_cases")
    builder.button(text="🏠 В меню", callback_data="to_menu")
    builder.adjust(1)

    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()
