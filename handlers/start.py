import logging
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery
from config import config
from keyboards.common import start_keyboard
from utils import texts

router = Router()
LEGACY_PUBLIC_CALLBACKS = {
    "reglament_reply",
    "programs_reply",
    "get_prices",
    "start_diagnostic",
    "start_apply",
    "show_cases",
    "to_menu",
    "back",
}

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info("User started the bot: user_id=%s", message.from_user.id)
    
    if config.START_PHOTO_FILE_ID:
        try:
            await message.answer_photo(
                photo=config.START_PHOTO_FILE_ID,
                caption=texts.START_MESSAGE,
                reply_markup=start_keyboard()
            )
        except Exception as e:
            logging.error("Failed to send start photo: %s", type(e).__name__)
            await message.answer(texts.START_MESSAGE, reply_markup=start_keyboard())
    else:
        await message.answer(texts.START_MESSAGE, reply_markup=start_keyboard())


@router.callback_query(F.data.in_(LEGACY_PUBLIC_CALLBACKS) | F.data.startswith("case_"))
async def cb_legacy_public_flow_disabled(query: CallbackQuery):
    if query.message:
        await query.message.answer(
            texts.LEGACY_PUBLIC_FLOW_DISABLED,
            reply_markup=start_keyboard(),
        )
    await query.answer()
