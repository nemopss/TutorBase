import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from config import config
from keyboards.common import start_keyboard
from utils import texts

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info(f"User {message.from_user.id} ({message.from_user.full_name}) started the bot.")
    
    if config.START_PHOTO_FILE_ID:
        try:
            await message.answer_photo(
                photo=config.START_PHOTO_FILE_ID,
                caption=texts.START_MESSAGE,
                reply_markup=start_keyboard()
            )
        except Exception as e:
            logging.error(f"Failed to send start photo: {e}")
            await message.answer(texts.START_MESSAGE, reply_markup=start_keyboard())
    else:
        await message.answer(texts.START_MESSAGE, reply_markup=start_keyboard())
