import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from keyboards.common import start_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info(f"User {message.from_user.id} ({message.from_user.full_name}) started the bot.")
    text = (
        'Привет! Я бот для приёма заявок на занятия по английскому и корейскому у Ксюшки!).\n\n'
        'Выбери, что хочешь сделать ниже.'
    )
    await message.answer(text, reply_markup=start_keyboard())
