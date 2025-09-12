import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config

router = Router()

class DiagnosticStates(StatesGroup):
    convenient_time = State()

@router.callback_query(F.data == "get_prices")
async def cb_get_prices(query: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, записаться", callback_data="start_diagnostic")
    builder.button(text="⬅️ В меню", callback_data="to_menu")
    builder.adjust(1)

    text = (
        "Цена зависит от формата обучения и других факторов, "
        "которые мы как раз подробно обсудим на диагностике ☺️\n\n"
        "Она будет бесплатная. Готов записаться?"
    )

    # Заменяем текущее сообщение на новое, с предложением диагностики
    await query.message.edit_text(text, reply_markup=builder.as_markup())
    await query.answer()


@router.callback_query(F.data == "start_diagnostic")
async def cb_start_diagnostic(query: CallbackQuery, state: FSMContext):
    # Создаем клавиатуру с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="get_prices") # Возвращает к предыдущему шагу

    await query.message.edit_text(
        "Отлично! Напишите удобный день и время для созвона (например: 'завтра после 15:00' или 'сб/вс в любое время').",
        reply_markup=builder.as_markup()
    )
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
        f"🔔 Новая запись на диагностику!\n\n"
        f"👤 **Пользователь:** {contact_info}\n"
        f"⏰ **Удобное время:** {message.text.strip()}"
    )

    # Отправляем уведомление в админ-чат
    try:
        # Редактируем прошлое сообщение бота, чтобы убрать кнопки
        data = await state.get_data()
        last_bot_msg_id = data.get("last_bot_msg_id") # Мы не сохраняли ID, так что это не сработает

        # Вместо редактирования, просто отправим новое сообщение и удалим старое, если нужно
        # Но для простоты, пока просто отправим новое.
        await message.bot.send_message(config.ADMIN_CHAT_ID, admin_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to send diagnostic notification to admin {config.ADMIN_CHAT_ID}: {e}")

    # Завершаем анкету и благодарим пользователя
    await state.clear()
    await message.answer(
        "Спасибо! Я передал вашу заявку, скоро с вами свяжутся для подтверждения времени ☺️"
    )




