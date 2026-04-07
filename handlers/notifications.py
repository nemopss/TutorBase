import logging
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.application.dto import NotificationResponseDraft
from notifications.application.responses import RecordNotificationResponseUseCase
from notifications.infrastructure.models import NotificationInstance
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork
from utils import texts


router = Router()


class NotificationResponseStates(StatesGroup):
    decline_reason = State()


@router.callback_query(F.data.startswith("notif_confirm_lesson_"))
async def cb_notification_confirm_lesson(query: CallbackQuery, session: AsyncSession):
    instance_id = _parse_instance_id(query.data, prefix="notif_confirm_lesson_")
    if instance_id is None:
        await query.answer("Неверный запрос", show_alert=True)
        return

    try:
        await _record_response(
            session,
            instance_id=instance_id,
            action_key="confirm_lesson",
            response_value="confirmed",
        )
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to persist notification confirm response #%s: %s", instance_id, exc)
        await query.answer(texts.DATABASE_ERROR, show_alert=True)
        return

    if query.message:
        await query.message.edit_reply_markup(None)
        await query.message.answer(texts.REMINDER_CONFIRM_REPLY)
    await query.answer()


@router.callback_query(F.data.startswith("notif_decline_lesson_"))
async def cb_notification_decline_lesson(query: CallbackQuery, state: FSMContext):
    instance_id = _parse_instance_id(query.data, prefix="notif_decline_lesson_")
    if instance_id is None:
        await query.answer("Неверный запрос", show_alert=True)
        return

    await state.set_state(NotificationResponseStates.decline_reason)
    await state.update_data(notification_instance_id=instance_id)
    if query.message:
        await query.message.edit_reply_markup(None)
        await query.message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
    await query.answer()


@router.message(NotificationResponseStates.decline_reason)
async def state_notification_decline_reason(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
):
    if not message.text:
        await message.answer(texts.REMINDER_DECLINE_REASON_PROMPT)
        return

    data = await state.get_data()
    instance_id = data.get("notification_instance_id")
    if not isinstance(instance_id, int):
        await state.clear()
        await message.answer(texts.REMINDER_NOT_FOUND)
        return

    reason_text = message.text.strip()
    try:
        await _record_response(
            session,
            instance_id=instance_id,
            action_key="decline_lesson",
            response_value="declined",
            response_text=reason_text,
        )
    except Exception as exc:
        await session.rollback()
        logging.error("Failed to persist notification decline response #%s: %s", instance_id, exc)
        await message.answer(texts.DATABASE_ERROR)
        return

    await state.clear()
    await message.answer(texts.REMINDER_DECLINE_REPLY)


async def _record_response(
    session: AsyncSession,
    *,
    instance_id: int,
    action_key: str,
    response_value: str,
    response_text: str | None = None,
) -> None:
    tenant_id = await _tenant_id_for_instance(session, instance_id)
    if tenant_id is None:
        raise ValueError(f"Notification instance {instance_id} not found")
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=tenant_id)
    await RecordNotificationResponseUseCase(uow).execute(
        NotificationResponseDraft(
            notification_instance_id=instance_id,
            action_key=action_key,
            response_value=response_value,
            response_text=response_text,
            response_metadata={"recorded_at": datetime.now(timezone.utc).isoformat()},
        )
    )


async def _tenant_id_for_instance(session: AsyncSession, instance_id: int) -> int | None:
    result = await session.execute(
        select(NotificationInstance.tenant_id).where(NotificationInstance.id == instance_id)
    )
    return result.scalar_one_or_none()


def _parse_instance_id(data: str | None, *, prefix: str) -> int | None:
    if not data or not data.startswith(prefix):
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None
