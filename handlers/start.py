import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from keyboards.common import start_keyboard
from utils import texts

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info(f"User {message.from_user.id} ({message.from_user.full_name}) started the bot.")
    await message.answer(texts.START_MESSAGE, reply_markup=start_keyboard())
