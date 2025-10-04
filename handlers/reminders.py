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


@router.callback_query(F.data.startswith('remi_confirm_'))
async def cb_reminder_instance_confirm(query: CallbackQuery, session: AsyncSession):
    instance_id = int(query.data.split('_')[-1])
    instance = await crud.get_reminder_instance(session, instance_id)
    if not instance:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    now_utc = datetime.now(timezone.utc)
    try:
        await crud.set_reminder_instance_status(
            session,
            instance,
            status='responded',
            active=False,
            last_response='confirmed',
            last_response_at=now_utc,
            last_decline_reason=None,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error(
            "Failed to persist confirm response for reminder instance #%s: %s",
            instance_id,
            exc,
        )
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    await query.message.edit_reply_markup(None)
    await query.message.answer(texts.REMINDER_CONFIRM_REPLY)
    student_name = escape_html_text(
        (instance.payload or {}).get('student_name')
        or (instance.learner.display_name if instance.learner else '—')
    )
    try:
        log_text = texts.REMINDER_CONFIRM_LOG.format(
            name=student_name,
            mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
        )
        await query.bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as exc:
        logging.error("Failed to send reminder instance confirm log: %s", exc)

    await query.answer()


@router.callback_query(F.data.startswith('remi_decline_'))
async def cb_reminder_instance_decline(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    instance_id = int(query.data.split('_')[-1])
    instance = await crud.get_reminder_instance(session, instance_id)
    if not instance:
        await query.answer(texts.REMINDER_NOT_FOUND, show_alert=True)
        return

    await state.set_state(ReminderResponseStates.reason)
    await state.update_data(instance_id=instance.id)
    await query.message.edit_reply_markup(None)
    await query.message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
    await query.answer()


@router.message(ReminderResponseStates.reason)
async def state_decline_reason(message: types.Message, state: FSMContext, session: AsyncSession):
    if not message.text:
        await message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
        return

    data = await state.get_data()
    instance_id = data.get('instance_id')

    instance = await crud.get_reminder_instance(session, instance_id)
    if not instance:
        await state.clear()
        await message.answer(texts.REMINDER_NOT_FOUND)
        return

    reason_text = message.text.strip()
    now_utc = datetime.now(timezone.utc)
    try:
        await crud.set_reminder_instance_status(
            session,
            instance,
            status='responded',
            active=False,
            last_response='declined',
            last_response_at=now_utc,
            last_decline_reason=reason_text,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logging.error(
            "Failed to persist decline response for reminder instance #%s: %s",
            instance_id,
            exc,
        )
        await message.answer(texts.DATABASE_ERROR)
        return

    student_name = escape_html_text(
        (instance.payload or {}).get('student_name')
        or (instance.learner.display_name if instance.learner else '—')
    )
    try:
        log_text = texts.REMINDER_DECLINE_LOG.format(
            name=student_name,
            reason=escape_html_text(reason_text),
            mention=escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME),
        )
        await message.bot.send_photo(
            config.LOGS_CHAT_ID,
            photo=config.CANCELLATION_IMAGE_FILE_ID,
            caption=log_text,
        )
    except Exception as exc:
        logging.error("Failed to send reminder instance decline log: %s", exc)

    await state.clear()
    await message.answer(texts.REMINDER_DECLINE_REPLY)
