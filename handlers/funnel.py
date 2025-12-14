import logging

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from utils import texts
from utils.formatters import escape_html_text
from keyboards.common import start_keyboard

router = Router()

class DiagnosticStates(StatesGroup):
    convenient_time = State()

@router.callback_query(F.data == "get_prices")
async def cb_get_prices(query: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, записаться", callback_data="start_diagnostic")
    builder.button(text="⬅️ В меню", callback_data="to_menu")
    builder.adjust(1)

    try:
        await query.message.edit_text(texts.GET_PRICES_TEXT, reply_markup=builder.as_markup())
    except TelegramBadRequest as e:
        if "there is no text in the message to edit" in e.message:
            await query.message.edit_caption(caption=texts.GET_PRICES_TEXT, reply_markup=builder.as_markup())
        else:
            raise
    finally:
        await query.answer()


@router.callback_query(F.data == "start_diagnostic")
async def cb_start_diagnostic(query: CallbackQuery, state: FSMContext):
    # Создаем клавиатуру с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="get_prices")  # Возвращает к предыдущему шагу
    builder.button(text="🏠 В меню", callback_data="to_menu")
    builder.adjust(1)

    prompt_msg = await query.message.edit_text(
        texts.PROMPT_FOR_DIAGNOSTIC_TIME,
        reply_markup=builder.as_markup()
    )
    await state.set_data({'last_bot_msg_id': prompt_msg.message_id})
    await state.set_state(DiagnosticStates.convenient_time)
    await query.answer()

@router.message(DiagnosticStates.convenient_time, F.text)
async def state_diagnostic_time(message: types.Message, state: FSMContext):
    # Удаляем сообщение пользователя для чистоты
    await message.delete()

    # Получаем контакт пользователя (username или ссылка)
    user = message.from_user
    contact_info = f"@{user.username}" if user.username else f"tg://user?id={user.id}"

    # Формируем текст заявки для администратора
    admin_text = (
        "🔔 Новая запись на диагностику!\n\n"
        f"👤 <b>Пользователь:</b> {escape_html_text(contact_info, default='—')}\n"
        f"⏰ <b>Удобное время:</b> {escape_html_text(message.text.strip(), default='—')}"
    )

    # Отправляем уведомление в админ-чат
    try:
        data = await state.get_data()
        last_bot_msg_id = data.get("last_bot_msg_id")
        if last_bot_msg_id:
            await message.bot.delete_message(message.chat.id, last_bot_msg_id)

        await message.bot.send_message(config.ADMIN_CHAT_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send diagnostic notification to admin {config.ADMIN_CHAT_ID}: {e}")

    # Завершаем анкету и благодарим пользователя
    await state.clear()
    await message.answer(
        texts.DIAGNOSTIC_SUBMITTED,
        reply_markup=start_keyboard()
    )


