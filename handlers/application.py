import logging
from datetime import datetime

from zoneinfo import ZoneInfo

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database.db import insert_application
from keyboards.common import start_keyboard, reglament_keyboard, back_keyboard
from utils.formatters import format_application

router = Router()

@router.callback_query(F.data == "to_menu")
async def cb_to_menu(query: CallbackQuery, state: FSMContext):
    logging.info(f"User {query.from_user.id} (@{query.from_user.username}) cancelled application process.")
    await state.clear()  # Сбрасываем анкету
    text = (
        'Привет! Я бот для приёма заявок на занятия по английскому и корейскому у Ксюшки!).\n\n'
        'Выбери, что хочешь сделать ниже.'
    )
    await query.message.edit_text(text, reply_markup=start_keyboard())
    await query.answer()


@router.callback_query(F.data == "reglament_reply")
async def cb_reglament_reply(query: CallbackQuery):
    text = """
        ❗️❗️каждому ученику обязательно нужно ознакомиться повторно с обновленными регламентами работы и написать мне после ознакомления🤲🏻
        это сайт, для того, чтобы прочитать пункты нужно нажать на треугольник рядом с каждым из них 
        в некоторых пунктах есть ещё и подпункты — обращайте внимание 
        *если не открывается, попробуйте отключиться от вай фая, переключиться на LTE и либо выключить впн, либо наоборот его включить
        приятного прочтения! ✨
        """
    await query.message.answer(text=text, reply_markup=reglament_keyboard())
    await query.answer()

class ApplyStates(StatesGroup):
    name = State()
    language = State()
    level = State()
    preferred_time = State()
    contact = State()


@router.callback_query(F.data == "back")
async def cb_back(query: CallbackQuery, state: FSMContext):
    current_state_str = await state.get_state()
    new_msg = None

    if current_state_str == ApplyStates.language.state:
        await state.set_state(ApplyStates.name)
        new_msg = await query.message.edit_text("Хорошо! Как к тебе обращаться? (имя)")

    elif current_state_str == ApplyStates.level.state:
        await state.set_state(ApplyStates.language)
        builder = InlineKeyboardBuilder()
        builder.button(text="Английский", callback_data="lang_en")
        builder.button(text="Корейский", callback_data="lang_kr")
        builder.button(text="⬅️ Назад", callback_data="back")
        builder.adjust(2, 1)
        new_msg = await query.message.edit_text("Выбери язык занятия:", reply_markup=builder.as_markup())

    elif current_state_str == ApplyStates.preferred_time.state:
        await state.set_state(ApplyStates.level)
        new_msg = await query.message.edit_text(
            "Какой у тебя уровень? (например: A1, A2, B1, Intermediate, Beginner и т.д.)",
            reply_markup=back_keyboard()
        )

    if new_msg:
        await state.update_data(last_bot_msg_id=new_msg.message_id)

    await query.answer()


@router.callback_query(F.data == "start_apply")
async def cb_start_apply(query: CallbackQuery, state: FSMContext):
    logging.info(f"User {query.from_user.id} (@{query.from_user.username}) started application process.")

    # Создаем клавиатуру с одной кнопкой "Меню"
    menu_button_builder = InlineKeyboardBuilder()
    menu_button_builder.button(text='⬅️ В меню', callback_data='to_menu')

    # Редактируем сообщение, убирая кнопки, и задаем первый вопрос с кнопкой "Меню"
    prompt_msg = await query.message.edit_text(
        "Хорошо! Как к тебе обращаться? (имя)",
        reply_markup=menu_button_builder.as_markup()
    )
    await state.set_data({'last_bot_msg_id': prompt_msg.message_id})
    await state.set_state(ApplyStates.name)
    await query.answer()



@router.message(ApplyStates.name, F.text)
async def state_name(message: types.Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    last_bot_msg_id = data.get("last_bot_msg_id")

    builder = InlineKeyboardBuilder()
    builder.button(text="Английский", callback_data="lang_en")
    builder.button(text="Корейский", callback_data="lang_kr")
    builder.button(text="⬅️ Назад", callback_data="back")
    builder.adjust(2, 1)

    prompt_msg = await message.bot.edit_message_text(
        text="Выбери язык занятия:",
        chat_id=message.chat.id,
        message_id=last_bot_msg_id,
        reply_markup=builder.as_markup()
    )
    await state.update_data(name=message.text.strip(), last_bot_msg_id=prompt_msg.message_id)
    await state.set_state(ApplyStates.language)

@router.callback_query(F.data.startswith("lang_"))
async def cb_language(query: CallbackQuery, state: FSMContext):
    lang = "English" if query.data == "lang_en" else "Korean"

    prompt_msg = await query.message.edit_text(
        "Какой у тебя уровень? (например: A1, A2, B1, Intermediate, Beginner и т.д.)",
        reply_markup=back_keyboard()
    )
    await state.update_data(language=lang, last_bot_msg_id=prompt_msg.message_id)
    await state.set_state(ApplyStates.level)
    await query.answer()


@router.message(ApplyStates.level, F.text)
async def state_level(message: types.Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    last_bot_msg_id = data.get("last_bot_msg_id")

    prompt_msg = await message.bot.edit_message_text(
        text="Удобное время для занятий (например: пн/ср 18:00-20:00 или утро/вечер):",
        chat_id=message.chat.id,
        message_id=last_bot_msg_id,
        reply_markup=back_keyboard()
    )
    await state.update_data(level=message.text.strip(), last_bot_msg_id=prompt_msg.message_id)
    await state.set_state(ApplyStates.preferred_time)


@router.message(ApplyStates.preferred_time, F.text)
async def state_time(message: types.Message, state: FSMContext):
    await message.delete()
    user_data = await state.get_data()
    last_bot_msg_id = user_data.get("last_bot_msg_id")

    if last_bot_msg_id:
        await message.bot.delete_message(message.chat.id, last_bot_msg_id)

    # --- Автоматическое получение контакта ---
    user = message.from_user
    contact_info = f"@{user.username}" if user.username else f"tg://user?id={user.id}"
    # ---

    msk_now = datetime.now(ZoneInfo("Europe/Moscow"))
    app_data = {
        "created_at": msk_now.strftime("%Y-%m-%d %H:%M:%S MSK"),
        "name": user_data.get("name"),
        "language": user_data.get("language"),
        "level": user_data.get("level"),
        "preferred_time": message.text.strip(),
        "contact": contact_info,
    }

    await insert_application(app_data)
    logging.info(f"User {user.id} successfully submitted application for language '{app_data['language']}'.")

    text = format_application(app_data)
    try:
        await message.bot.send_message(config.ADMIN_CHAT_ID, text)
    except Exception as e:
        logging.error(f"Failed to send notification to admin {config.ADMIN_CHAT_ID}: {e}")

    await message.answer(
        "Спасибо! Твоя заявка принята. Мы свяжемся с тобой в ближайшее время.",
    )
    await state.clear()
