from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BotUser, ReminderInstance
from filters.admin import IsAdmin
from keyboards.common import admin_keyboard
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk
from utils.state import get_bot_started_at


router = Router()


@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: types.Message):
    await message.answer(texts.ADMIN_PANEL, reply_markup=admin_keyboard())


@router.message(Command("status"), IsAdmin())
async def cmd_status(message: types.Message, session: AsyncSession):
    started_at = get_bot_started_at()
    started_label = format_timestamp_msk(started_at) if started_at else "—"
    total_users = await _count_bot_users(session)
    scheduled_reminders = await _count_reminders(session, status="scheduled")
    total_reminders = await _count_reminders(session)

    await message.answer(
        texts.STATUS_REPORT.format(
            started_at=escape_html_text(started_label),
            active_reminders=escape_html_text(scheduled_reminders),
            total_reminders=escape_html_text(total_reminders),
            total_users=escape_html_text(total_users),
        )
    )


@router.message(Command("admin"))
@router.message(Command("status"))
async def cmd_admin_denied(message: types.Message):
    await message.answer(texts.ACCESS_DENIED)


async def _count_bot_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(BotUser))
    return int(result.scalar_one() or 0)


async def _count_reminders(session: AsyncSession, *, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(ReminderInstance)
    if status is not None:
        stmt = stmt.where(ReminderInstance.status == status)
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)
