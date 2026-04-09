import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Learner, Lesson, User
from notifications.application.dto import NotificationResponseDraft
from notifications.application.responses import RecordNotificationResponseUseCase
from notifications.infrastructure.models import NotificationInstance
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk


router = Router()


@dataclass(frozen=True)
class NotificationResponseContext:
    tenant_id: int
    learner_name: str
    event_type: str
    lesson_scheduled_at: datetime | None = None


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
    await _notify_about_response(
        query.bot,
        session,
        instance_id=instance_id,
        response_value="confirmed",
    )
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
    await _notify_about_response(
        message.bot,
        session,
        instance_id=instance_id,
        response_value="declined",
        response_text=reason_text,
    )


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


async def _notify_about_response(
    bot,
    session: AsyncSession,
    *,
    instance_id: int,
    response_value: str,
    response_text: str | None = None,
) -> None:
    context = await _notification_response_context(session, instance_id)
    if context is None:
        logging.warning("Notification response context not found for instance #%s", instance_id)
        return

    teacher_text = _build_teacher_response_message(
        context,
        response_value=response_value,
        response_text=response_text,
    )
    log_text = _build_response_log_message(
        context,
        response_value=response_value,
        response_text=response_text,
    )

    await _safe_send_message(
        bot,
        chat_id=config.LOGS_CHAT_ID,
        text=log_text,
        label=f"log chat for notification response #{instance_id}",
    )

    for chat_id in await _teacher_recipient_ids_for_tenant(session, context.tenant_id):
        if chat_id == config.LOGS_CHAT_ID:
            continue
        await _safe_send_message(
            bot,
            chat_id=chat_id,
            text=teacher_text,
            label=f"teacher notification response #{instance_id} to {chat_id}",
        )


async def _notification_response_context(
    session: AsyncSession,
    instance_id: int,
) -> NotificationResponseContext | None:
    result = await session.execute(
        select(
            NotificationInstance.tenant_id,
            NotificationInstance.event_type,
            Learner.display_name.label("learner_name"),
            Lesson.scheduled_at.label("lesson_scheduled_at"),
        )
        .select_from(NotificationInstance)
        .outerjoin(Learner, Learner.id == NotificationInstance.learner_id)
        .outerjoin(
            Lesson,
            and_(
                NotificationInstance.event_type == "lesson",
                Lesson.id == NotificationInstance.event_id,
            ),
        )
        .where(NotificationInstance.id == instance_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return NotificationResponseContext(
        tenant_id=row.tenant_id,
        learner_name=row.learner_name or "Ученик",
        event_type=row.event_type,
        lesson_scheduled_at=row.lesson_scheduled_at,
    )


async def _teacher_recipient_ids_for_tenant(session: AsyncSession, tenant_id: int) -> tuple[int, ...]:
    result = await session.execute(
        select(User.telegram_id)
        .where(
            User.tenant_id == tenant_id,
            User.role.in_(("teacher", "admin")),
            User.telegram_id.is_not(None),
        )
        .order_by(User.id)
    )
    values = [int(value) for value in result.scalars().all() if value is not None]
    return tuple(dict.fromkeys(values))


def _build_teacher_response_message(
    context: NotificationResponseContext,
    *,
    response_value: str,
    response_text: str | None = None,
) -> str:
    learner_name = escape_html_text(context.learner_name)
    if response_value == "declined":
        lines = [f"Ученик <b>{learner_name}</b> отказался от урока."]
        lesson_line = _lesson_time_line(context.lesson_scheduled_at)
        if lesson_line:
            lines.append(lesson_line)
        if response_text:
            lines.append(f"Причина: {escape_html_text(response_text)}")
        return "\n".join(lines)

    if response_value == "confirmed":
        lines = [f"Ученик <b>{learner_name}</b> подтвердил урок."]
        lesson_line = _lesson_time_line(context.lesson_scheduled_at)
        if lesson_line:
            lines.append(lesson_line)
        return "\n".join(lines)

    return (
        f"Ученик <b>{learner_name}</b> отправил ответ по уведомлению: "
        f"<b>{escape_html_text(response_value)}</b>."
    )


def _build_response_log_message(
    context: NotificationResponseContext,
    *,
    response_value: str,
    response_text: str | None = None,
) -> str:
    learner_name = escape_html_text(context.learner_name)
    if response_value == "declined":
        lines = [
            "#notification_decline",
            f"Ученик: {learner_name}",
            "Ответ: отказался от урока",
        ]
        lesson_line = _lesson_time_line(context.lesson_scheduled_at)
        if lesson_line:
            lines.append(lesson_line)
        if response_text:
            lines.append(f"Причина: {escape_html_text(response_text)}")
        mention = _notify_mention()
        if mention:
            lines.append(mention)
        return "\n".join(lines)

    if response_value == "confirmed":
        lines = [
            "#notification_confirm",
            f"Ученик: {learner_name}",
            "Ответ: подтвердил урок",
        ]
        lesson_line = _lesson_time_line(context.lesson_scheduled_at)
        if lesson_line:
            lines.append(lesson_line)
        mention = _notify_mention()
        if mention:
            lines.append(mention)
        return "\n".join(lines)

    lines = [
        "#notification_response",
        f"Ученик: {learner_name}",
        f"Ответ: {escape_html_text(response_value)}",
    ]
    mention = _notify_mention()
    if mention:
        lines.append(mention)
    return "\n".join(lines)


def _lesson_time_line(value: datetime | None) -> str | None:
    if value is None:
        return None
    return f"Урок: {escape_html_text(format_timestamp_msk(value))}"


def _notify_mention() -> str | None:
    if not config.REMINDER_NOTIFY_USERNAME:
        return None
    return f"@{escape_html_text(config.REMINDER_NOTIFY_USERNAME, default=config.REMINDER_NOTIFY_USERNAME)}"


async def _safe_send_message(bot, *, chat_id: int, text: str, label: str) -> None:
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception as exc:
        logging.error("Failed to send %s: %s", label, exc)
