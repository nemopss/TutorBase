import logging
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database import crud
from utils import texts
from utils.formatters import escape_html_text


router = Router()


class ReminderResponseStates(StatesGroup):
    reason = State()


@router.callback_query(F.data.startswith('rem_confirm_'))
async def cb_reminder_confirm(query: CallbackQuery, session: AsyncSession):
    reminder_id = int(query.data.split('_')[-1])
    reminder = await crud.get_lesson_reminder(session, reminder_id)
    if not reminder:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    reminder.last_response = 'confirmed'
    reminder.last_response_at = datetime.now(timezone.utc)
    reminder.last_decline_reason = None

    try:
        await crud.save_lesson_reminder(session, reminder)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error(
            "Failed to persist confirm response for reminder #%s: %s",
            reminder_id,
            exc,
        )
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    await query.message.edit_reply_markup(None)
    await query.message.answer(texts.REMINDER_CONFIRM_REPLY)
    try:
        log_text = texts.REMINDER_CONFIRM_LOG.format(
            name=escape_html_text(reminder.student_name),
            mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
        )
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as exc:
        logging.error(f"Failed to send reminder confirm log: {exc}")

    await query.answer()


@router.callback_query(F.data.startswith('rem_decline_'))
async def cb_reminder_decline(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    reminder_id = int(query.data.split('_')[-1])
    reminder = await crud.get_lesson_reminder(session, reminder_id)
    if not reminder:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(ReminderResponseStates.reason)
    await state.update_data(reminder_id=reminder.id)
    await query.message.edit_reply_markup(None)
    await query.message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
    await query.answer()


@router.message(ReminderResponseStates.reason)
async def state_decline_reason(message: types.Message, state: FSMContext, session: AsyncSession):
    if not message.text:
        await message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
        return

    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    reminder = await crud.get_lesson_reminder(session, reminder_id)
    if not reminder:
        await state.clear()
        await message.answer(texts.REMINDER_NOT_FOUND)
        return

    reminder.last_response = 'declined'
    reminder.last_response_at = datetime.now(timezone.utc)
    reminder.last_decline_reason = message.text.strip()

    try:
        await crud.save_lesson_reminder(session, reminder)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error(
            "Failed to persist decline response for reminder #%s: %s",
            reminder_id,
            exc,
        )
        await message.answer(texts.DATABASE_ERROR)
        return

    try:
        log_text = texts.REMINDER_DECLINE_LOG.format(
            name=escape_html_text(reminder.student_name),
            reason=escape_html_text(reminder.last_decline_reason),
            mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
        )
        await message.bot.send_photo(
            config.LOGS_CHAT_ID,
            photo=config.CANCELLATION_IMAGE_FILE_ID,
            caption=log_text
        )
    except Exception as exc:
        logging.error(f"Failed to send reminder decline log: {exc}")

    await state.clear()
    await message.answer(texts.REMINDER_DECLINE_REPLY)
