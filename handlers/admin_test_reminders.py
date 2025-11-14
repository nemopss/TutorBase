"""Admin handlers for testing reminder notifications.

This module provides functionality for administrators to test reminder notifications
by sending test copies of all reminders for a package to a specified contact.
"""
import logging
import asyncio
from typing import Optional

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database import crud
from filters.admin import IsAdmin
from utils import texts
from utils.formatters import escape_html_text, format_timestamp_msk

router = Router()

# Pagination settings
PACKAGES_PER_PAGE = 5


class TestReminderStates(StatesGroup):
    """FSM states for test reminder workflow."""
    waiting_for_contact = State()



# ============================================================================
# Helper Functions
# ============================================================================


def _calc_total_pages(total: int, per_page: int) -> int:
    """Calculate total number of pages for pagination."""
    if total <= 0:
        return 1
    import math
    return max(1, math.ceil(total / per_page))


def _add_pagination(builder: InlineKeyboardBuilder, page: int, total_pages: int, prefix: str) -> None:
    """Add pagination buttons to keyboard."""
    if total_pages <= 1:
        return
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text='⬅️', callback_data=f'{prefix}:{page - 1}'))
    buttons.append(InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text='➡️', callback_data=f'{prefix}:{page + 1}'))
    builder.row(*buttons)


async def _count_active_reminders_for_package(session: AsyncSession, package_id: int) -> int:
    """Count active reminders for a package."""
    from sqlalchemy import select, func
    from database.models import ReminderInstance
    
    stmt = select(func.count()).where(
        ReminderInstance.package_id == package_id,
        ReminderInstance.status == 'scheduled',
        ReminderInstance.active == True
    )
    result = await session.execute(stmt)
    return result.scalar_one()


def _format_packages_menu_text(packages, page: int, total_pages: int, total_count: int, reminder_counts: dict) -> str:
    """Format text for packages menu."""
    if not packages:
        return texts.TEST_PACKAGES_EMPTY
    
    lines = [texts.TEST_REMINDERS_MENU, ""]
    
    start_index = (page - 1) * PACKAGES_PER_PAGE + 1
    for idx, package in enumerate(packages, start=start_index):
        learner_name = package.learner.display_name if package.learner else "—"
        count = reminder_counts.get(package.id, 0)
        
        item_text = texts.TEST_PACKAGE_ITEM.format(
            title=escape_html_text(package.title),
            learner_name=escape_html_text(learner_name),
            count=count
        )
        lines.append(f"{idx}. {item_text}")
        lines.append("")
    
    lines.append(f"Страница {page}/{total_pages}")
    return "\n".join(lines)


def _build_packages_keyboard(packages, page: int, total_pages: int, reminder_counts: dict) -> InlineKeyboardBuilder:
    """Build keyboard for packages menu."""
    builder = InlineKeyboardBuilder()
    
    for package in packages:
        count = reminder_counts.get(package.id, 0)
        learner_name = package.learner.display_name if package.learner else "—"
        button_text = f"📦 {package.title} ({learner_name}, {count})"
        builder.button(
            text=button_text[:60],  # Truncate if too long
            callback_data=f"test_package:{package.id}:{page}"
        )
    
    if packages:
        builder.adjust(1)
    
    _add_pagination(builder, page, total_pages, 'test_packages_page')
    builder.row(InlineKeyboardButton(text='⬅️ Назад в админ-панель', callback_data='back_to_admin_panel'))
    
    return builder


# ============================================================================
# Handlers
# ============================================================================


@router.callback_query(F.data == 'test_reminders', IsAdmin())
async def cb_test_reminders_menu(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Show test reminders menu with list of packages."""
    logging.info(f"Admin {query.from_user.id} opened test reminders menu")
    
    # Clear any existing state
    await state.clear()
    
    # Fetch packages with active reminders
    page = 1
    offset = (page - 1) * PACKAGES_PER_PAGE
    
    # Create a mock CurrentTenant for now (will be replaced with proper tenant support)
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    packages, total = await crud.fetch_packages_with_active_reminders(
        session,
        current_tenant,
        limit=PACKAGES_PER_PAGE,
        offset=offset
    )
    
    # Count reminders for each package
    reminder_counts = {}
    for package in packages:
        count = await _count_active_reminders_for_package(session, package.id)
        reminder_counts[package.id] = count
    
    total_pages = _calc_total_pages(total, PACKAGES_PER_PAGE)
    
    text = _format_packages_menu_text(packages, page, total_pages, total, reminder_counts)
    markup = _build_packages_keyboard(packages, page, total_pages, reminder_counts).as_markup()
    
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)
    
    await query.answer()



@router.callback_query(F.data.startswith('test_packages_page:'), IsAdmin())
async def cb_test_packages_page(query: CallbackQuery, session: AsyncSession):
    """Handle pagination for packages list."""
    try:
        page = int(query.data.split(':')[1])
    except (IndexError, ValueError):
        page = 1
    
    logging.info(f"Admin {query.from_user.id} navigating to test packages page {page}")
    
    offset = (page - 1) * PACKAGES_PER_PAGE
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    packages, total = await crud.fetch_packages_with_active_reminders(
        session,
        current_tenant,
        limit=PACKAGES_PER_PAGE,
        offset=offset
    )
    
    # Count reminders for each package
    reminder_counts = {}
    for package in packages:
        count = await _count_active_reminders_for_package(session, package.id)
        reminder_counts[package.id] = count
    
    total_pages = _calc_total_pages(total, PACKAGES_PER_PAGE)
    
    # Adjust page if out of bounds
    if page > total_pages and total > 0:
        page = total_pages
        offset = (page - 1) * PACKAGES_PER_PAGE
        packages, total = await crud.fetch_packages_with_active_reminders(
            session,
            current_tenant,
            limit=PACKAGES_PER_PAGE,
            offset=offset
        )
        # Recount reminders
        reminder_counts = {}
        for package in packages:
            count = await _count_active_reminders_for_package(session, package.id)
            reminder_counts[package.id] = count
    
    text = _format_packages_menu_text(packages, page, total_pages, total, reminder_counts)
    markup = _build_packages_keyboard(packages, page, total_pages, reminder_counts).as_markup()
    
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)
    
    await query.answer()



def _describe_reminder_type(instance) -> str:
    """Get human-readable description of reminder type."""
    from services.reminder_definitions import (
        REMINDER_TYPE_LESSON_CONFIRM,
        REMINDER_TYPE_LESSON_DAY_BEFORE,
        REMINDER_TYPE_PAYMENT_WEEK,
        REMINDER_TYPE_PAYMENT_DAY,
        REMINDER_TYPE_HOMEWORK,
        REMINDER_TYPE_PACKAGE_RENEWAL,
    )
    
    reminder_type = getattr(instance.rule, 'reminder_type', '') if instance.rule else ''
    
    if reminder_type == REMINDER_TYPE_LESSON_CONFIRM:
        return texts.REMINDER_TYPE_RECURRING
    if reminder_type == REMINDER_TYPE_LESSON_DAY_BEFORE:
        return texts.REMINDER_TYPE_LESSON_DAY_BEFORE
    if reminder_type == REMINDER_TYPE_PAYMENT_WEEK:
        return texts.REMINDER_TYPE_PAYMENT_WEEK
    if reminder_type == REMINDER_TYPE_PAYMENT_DAY:
        return texts.REMINDER_TYPE_PAYMENT_DAY
    if reminder_type == REMINDER_TYPE_HOMEWORK:
        return texts.REMINDER_TYPE_HOMEWORK
    if reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL:
        return texts.REMINDER_TYPE_PACKAGE_RENEWAL
    
    return reminder_type or "—"


def _format_package_details_text(package, reminders) -> str:
    """Format text for package details with reminders list."""
    learner_name = package.learner.display_name if package.learner else "—"
    
    start_date = format_timestamp_msk(package.start_date) if package.start_date else "—"
    end_date = format_timestamp_msk(package.end_date) if package.end_date else "—"
    
    if not reminders:
        return texts.TEST_PACKAGE_DETAILS.format(
            title=escape_html_text(package.title),
            learner_name=escape_html_text(learner_name),
            start_date=escape_html_text(start_date),
            end_date=escape_html_text(end_date),
            count=0,
            reminders_list=texts.TEST_NO_REMINDERS
        )
    
    reminders_lines = []
    for reminder in reminders:
        reminder_type = _describe_reminder_type(reminder)
        scheduled_for = format_timestamp_msk(reminder.scheduled_for) if reminder.scheduled_for else "—"
        
        item = texts.TEST_REMINDER_ITEM.format(
            type=escape_html_text(reminder_type),
            scheduled_for=escape_html_text(scheduled_for)
        )
        reminders_lines.append(item)
    
    reminders_list = "\n".join(reminders_lines)
    
    return texts.TEST_PACKAGE_DETAILS.format(
        title=escape_html_text(package.title),
        learner_name=escape_html_text(learner_name),
        start_date=escape_html_text(start_date),
        end_date=escape_html_text(end_date),
        count=len(reminders),
        reminders_list=reminders_list
    )


def _build_package_details_keyboard(package_id: int, page: int, has_reminders: bool) -> InlineKeyboardBuilder:
    """Build keyboard for package details view."""
    builder = InlineKeyboardBuilder()
    
    if has_reminders:
        builder.button(
            text='📨 Отправить все тесты',
            callback_data=f'test_package_send:{package_id}:{page}'
        )
    
    builder.button(
        text='⬅️ Назад к списку пакетов',
        callback_data=f'test_back_packages:{page}'
    )
    
    builder.adjust(1)
    return builder


@router.callback_query(F.data.startswith('test_package:'), IsAdmin())
async def cb_test_package_view(query: CallbackQuery, session: AsyncSession):
    """Show package details with list of active reminders."""
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer("Ошибка: некорректные данные", show_alert=True)
        return
    
    logging.info(f"Admin {query.from_user.id} viewing test package {package_id}")
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    # Fetch package
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        await query.answer("Пакет не найден", show_alert=True)
        return
    
    # Fetch active reminders for package
    reminders = await crud.fetch_active_reminders_for_package(session, current_tenant, package_id)
    
    text = _format_package_details_text(package, reminders)
    markup = _build_package_details_keyboard(package_id, page, len(reminders) > 0).as_markup()
    
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)
    
    await query.answer()



@router.callback_query(F.data.startswith('test_package_send:'), IsAdmin())
async def cb_test_package_send(query: CallbackQuery, state: FSMContext):
    """Start process of sending test reminders - request contact."""
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer("Ошибка: некорректные данные", show_alert=True)
        return
    
    logging.info(f"Admin {query.from_user.id} starting test send for package {package_id}")
    
    # Save package_id and page in state
    await state.update_data(package_id=package_id, page=page)
    await state.set_state(TestReminderStates.waiting_for_contact)
    
    # Show contact prompt
    builder = InlineKeyboardBuilder()
    builder.button(text='⬅️ Отмена', callback_data=f'test_cancel:{package_id}:{page}')
    
    try:
        await query.message.edit_text(texts.TEST_PROMPT_CONTACT, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await query.message.answer(texts.TEST_PROMPT_CONTACT, reply_markup=builder.as_markup())
    
    await query.answer()



@router.message(TestReminderStates.waiting_for_contact, F.text, IsAdmin())
async def state_test_reminder_contact(message: types.Message, state: FSMContext, session: AsyncSession):
    """Handle contact input and show confirmation."""
    from handlers.admin import ContactPayload
    
    data = await state.get_data()
    package_id = data.get('package_id')
    page = data.get('page', 1)
    
    if not package_id:
        await state.clear()
        await message.answer("Ошибка: данные сессии потеряны")
        return
    
    # Validate contact format
    contact_text = message.text.strip()
    
    try:
        # Import and use the validation function from admin.py
        from handlers.admin import _contact_to_payload
        contact_payload = _contact_to_payload(contact_text)
        contact_display = contact_payload.display
        contact_value = contact_payload.value
    except ValueError:
        # Invalid format
        builder = InlineKeyboardBuilder()
        builder.button(text='⬅️ Отмена', callback_data=f'test_cancel:{package_id}:{page}')
        await message.answer(texts.TEST_INVALID_CONTACT, reply_markup=builder.as_markup())
        return
    
    logging.info(f"Admin {message.from_user.id} entered contact {contact_display} for package {package_id}")
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    # Fetch package and reminders
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        await state.clear()
        await message.answer("Пакет не найден")
        return
    
    reminders = await crud.fetch_active_reminders_for_package(session, current_tenant, package_id)
    
    if not reminders:
        await state.clear()
        await message.answer("У пакета нет активных напоминаний")
        return
    
    # Save contact in state
    await state.update_data(contact_value=contact_value, contact_display=contact_display)
    
    # Show confirmation
    text = texts.TEST_CONFIRM.format(
        package_title=escape_html_text(package.title),
        count=len(reminders),
        contact=escape_html_text(contact_display)
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text='✅ Отправить все',
        callback_data=f'test_confirm_send:{package_id}:{contact_value}:{page}'
    )
    builder.button(
        text='⬅️ Отмена',
        callback_data=f'test_cancel:{package_id}:{page}'
    )
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())



def _build_test_reminder_message(instance, bot) -> tuple[Optional[str], Optional[types.InlineKeyboardMarkup]]:
    """Build test reminder message with prefix and scheduled date.
    
    Uses the same logic as ReminderScheduler._build_instance_message but adds
    test prefix and scheduled date information.
    
    Args:
        instance: ReminderInstance to build message for
        bot: Bot instance (not used but kept for consistency)
        
    Returns:
        Tuple of (message_text, keyboard_markup) where keyboard may be None
    """
    from services.reminder_definitions import (
        REMINDER_TYPE_LESSON_CONFIRM,
        REMINDER_TYPE_LESSON_DAY_BEFORE,
        REMINDER_TYPE_PAYMENT_WEEK,
        REMINDER_TYPE_PAYMENT_DAY,
        REMINDER_TYPE_HOMEWORK,
        REMINDER_TYPE_PACKAGE_RENEWAL,
    )
    from zoneinfo import ZoneInfo
    
    # Build schedule label
    lesson = instance.lesson
    tz_name = getattr(instance.package, 'timezone', 'Europe/Moscow') if instance.package else 'Europe/Moscow'
    
    if lesson and lesson.scheduled_at:
        schedule_label = format_timestamp_msk(lesson.scheduled_at)
    else:
        payload = instance.payload or {}
        if 'schedule_label' in payload:
            schedule_label = payload['schedule_label']
        elif instance.scheduled_for:
            schedule_label = format_timestamp_msk(instance.scheduled_for)
        else:
            schedule_label = '—'
    
    # Get student name
    payload = instance.payload or {}
    name = payload.get('student_name') or (instance.learner.display_name if instance.learner else '—')
    name = escape_html_text(name)
    
    # Build prefix with scheduled date
    scheduled_for_label = format_timestamp_msk(instance.scheduled_for) if instance.scheduled_for else '—'
    prefix = texts.TEST_MESSAGE_PREFIX.format(scheduled_for=escape_html_text(scheduled_for_label))
    
    # Build message based on type
    reminder_type = getattr(instance.rule, 'reminder_type', '') if instance.rule else ''
    
    if reminder_type == REMINDER_TYPE_LESSON_CONFIRM:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text=texts.REMINDER_CONFIRM_BUTTON, callback_data=f"test_remi_confirm_{instance.id}")
        keyboard.button(text=texts.REMINDER_DECLINE_BUTTON, callback_data=f"test_remi_decline_{instance.id}")
        keyboard.adjust(1)
        message = texts.REMINDER_TRIGGER_MESSAGE.format(
            name=name,
            schedule=escape_html_text(schedule_label),
        )
        return prefix + message, keyboard.as_markup()
    
    if reminder_type == REMINDER_TYPE_LESSON_DAY_BEFORE:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text=texts.REMINDER_CONFIRM_BUTTON, callback_data=f"test_remi_confirm_{instance.id}")
        keyboard.button(text=texts.REMINDER_DECLINE_BUTTON, callback_data=f"test_remi_decline_{instance.id}")
        keyboard.adjust(1)
        message = texts.REMINDER_DAY_BEFORE_MESSAGE.format(
            name=name,
            schedule=escape_html_text(schedule_label),
        )
        return prefix + message, keyboard.as_markup()
    
    if reminder_type == REMINDER_TYPE_PAYMENT_WEEK:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text=texts.PAYMENT_CONFIRM_BUTTON,
            callback_data=f"test_payment_confirm_{instance.id}"
        )
        keyboard.button(
            text=texts.PAYMENT_DECLINE_BUTTON,
            callback_data=f"test_payment_decline_{instance.id}"
        )
        keyboard.adjust(1)
        
        last_lesson_date = payload.get('last_lesson_date', '—')
        message = texts.PAYMENT_REMINDER_WEEK_BEFORE.format(
            name=name,
            last_lesson_date=escape_html_text(last_lesson_date),
        )
        return prefix + message, keyboard.as_markup()
    
    if reminder_type == REMINDER_TYPE_PAYMENT_DAY:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text=texts.PAYMENT_CONFIRM_BUTTON,
            callback_data=f"test_payment_confirm_{instance.id}"
        )
        keyboard.button(
            text=texts.PAYMENT_DECLINE_BUTTON,
            callback_data=f"test_payment_decline_{instance.id}"
        )
        keyboard.adjust(1)
        
        message = texts.PAYMENT_REMINDER_DAY_BEFORE.format(name=name)
        return prefix + message, keyboard.as_markup()
    
    if reminder_type == REMINDER_TYPE_HOMEWORK:
        message = texts.HOMEWORK_REMINDER_MESSAGE.format(
            name=name,
            schedule=escape_html_text(schedule_label),
        )
        return prefix + message, None
    
    if reminder_type == REMINDER_TYPE_PACKAGE_RENEWAL:
        end_label = payload.get('package_end') or schedule_label
        message = texts.PACKAGE_RENEWAL_REMINDER_MESSAGE.format(
            name=name,
            end_date=escape_html_text(end_label),
        )
        return prefix + message, None
    
    # Fallback to generic message
    message = texts.REMINDER_TRIGGER_MESSAGE.format(
        name=name,
        schedule=escape_html_text(schedule_label),
    )
    return prefix + message, None



@router.callback_query(F.data.startswith('test_confirm_send:'), IsAdmin())
async def cb_test_confirm_send(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Send all test reminders for the package."""
    try:
        _, package_id_str, contact_value, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer("Ошибка: некорректные данные", show_alert=True)
        return
    
    # Get contact display from state
    data = await state.get_data()
    contact_display = data.get('contact_display', contact_value)
    
    logging.info(f"Admin {query.from_user.id} confirming test send for package {package_id} to {contact_display}")
    
    # Clear state
    await state.clear()
    
    # Show "sending" message
    try:
        await query.message.edit_text(texts.TEST_SENDING)
    except TelegramBadRequest:
        await query.message.answer(texts.TEST_SENDING)
    
    await query.answer()
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    # Fetch package and reminders
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        await query.message.answer("Пакет не найден")
        return
    
    reminders = await crud.fetch_active_reminders_for_package(session, current_tenant, package_id)
    
    if not reminders:
        await query.message.answer("У пакета нет активных напоминаний")
        return
    
    # Resolve contact to chat_id
    # Parse contact_value to get actual target
    from utils.formatters import split_chat_identifier
    label, actual = split_chat_identifier(contact_value)
    target: Optional[int | str] = actual or label or None
    if isinstance(target, str) and target.lstrip('-').isdigit():
        target = int(target)
    
    if not target:
        await query.message.answer("Не удалось определить получателя")
        return
    
    # Send each reminder
    results = []
    success_count = 0
    error_count = 0
    
    bot = query.bot
    
    for reminder in reminders:
        reminder_type = _describe_reminder_type(reminder)
        scheduled_for = format_timestamp_msk(reminder.scheduled_for) if reminder.scheduled_for else "—"
        
        try:
            # Build test message
            message_text, keyboard = _build_test_reminder_message(reminder, bot)
            
            if not message_text:
                error_count += 1
                results.append(texts.TEST_RESULT_ERROR.format(
                    type=escape_html_text(reminder_type),
                    scheduled_for=escape_html_text(scheduled_for),
                    error="Пустое сообщение"
                ))
                continue
            
            # Send message
            await bot.send_message(target, message_text, reply_markup=keyboard)
            
            success_count += 1
            results.append(texts.TEST_RESULT_SUCCESS.format(
                type=escape_html_text(reminder_type),
                scheduled_for=escape_html_text(scheduled_for)
            ))
            
            # Delay between sends to avoid rate limits
            await asyncio.sleep(0.5)
            
        except TelegramBadRequest as exc:
            error_count += 1
            results.append(texts.TEST_RESULT_ERROR.format(
                type=escape_html_text(reminder_type),
                scheduled_for=escape_html_text(scheduled_for),
                error=f"Некорректный запрос: {exc}"
            ))
            logging.error(f"TelegramBadRequest sending test reminder {reminder.id}: {exc}")
            
        except TelegramForbiddenError as exc:
            error_count += 1
            results.append(texts.TEST_RESULT_ERROR.format(
                type=escape_html_text(reminder_type),
                scheduled_for=escape_html_text(scheduled_for),
                error="Пользователь заблокировал бота"
            ))
            logging.error(f"TelegramForbiddenError sending test reminder {reminder.id}: {exc}")
            
        except Exception as exc:
            error_count += 1
            results.append(texts.TEST_RESULT_ERROR.format(
                type=escape_html_text(reminder_type),
                scheduled_for=escape_html_text(scheduled_for),
                error=f"Ошибка сети: {exc}"
            ))
            logging.error(f"Error sending test reminder {reminder.id}: {exc}")
    
    # Show results
    details = "\n".join(results)
    result_text = texts.TEST_RESULTS.format(
        success_count=success_count,
        error_count=error_count,
        details=details
    )
    
    await query.message.answer(result_text)
    
    # Log to admin chat
    admin_user = query.from_user
    log_text = texts.TEST_LOG_MESSAGE.format(
        admin_username=escape_html_text(admin_user.username or str(admin_user.id)),
        admin_id=admin_user.id,
        package_title=escape_html_text(package.title),
        package_id=package_id,
        contact=escape_html_text(contact_display),
        success_count=success_count,
        error_count=error_count
    )
    
    try:
        await bot.send_message(config.LOGS_CHAT_ID, log_text)
    except Exception as exc:
        logging.error(f"Failed to send test reminders log: {exc}")



@router.callback_query(F.data.startswith('test_back_packages:'), IsAdmin())
async def cb_test_back_packages(query: CallbackQuery, session: AsyncSession):
    """Return to packages list."""
    try:
        page = int(query.data.split(':')[1])
    except (IndexError, ValueError):
        page = 1
    
    logging.info(f"Admin {query.from_user.id} returning to test packages page {page}")
    
    offset = (page - 1) * PACKAGES_PER_PAGE
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    packages, total = await crud.fetch_packages_with_active_reminders(
        session,
        current_tenant,
        limit=PACKAGES_PER_PAGE,
        offset=offset
    )
    
    # Count reminders for each package
    reminder_counts = {}
    for package in packages:
        count = await _count_active_reminders_for_package(session, package.id)
        reminder_counts[package.id] = count
    
    total_pages = _calc_total_pages(total, PACKAGES_PER_PAGE)
    
    text = _format_packages_menu_text(packages, page, total_pages, total, reminder_counts)
    markup = _build_packages_keyboard(packages, page, total_pages, reminder_counts).as_markup()
    
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)
    
    await query.answer()



@router.callback_query(F.data.startswith('test_cancel:'), IsAdmin())
async def cb_test_cancel(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Cancel test send and return to package details."""
    try:
        _, package_id_str, page_str = query.data.split(':')
        package_id = int(package_id_str)
        page = int(page_str)
    except (ValueError, IndexError):
        await query.answer("Ошибка: некорректные данные", show_alert=True)
        return
    
    logging.info(f"Admin {query.from_user.id} cancelling test send for package {package_id}")
    
    # Clear state
    await state.clear()
    
    # Create a mock CurrentTenant for now
    from api.dependencies import CurrentTenant
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    
    # Fetch package and reminders
    package = await crud.get_lesson_package(session, current_tenant, package_id)
    if not package:
        await query.answer("Пакет не найден", show_alert=True)
        return
    
    reminders = await crud.fetch_active_reminders_for_package(session, current_tenant, package_id)
    
    text = _format_package_details_text(package, reminders)
    markup = _build_package_details_keyboard(package_id, page, len(reminders) > 0).as_markup()
    
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await query.message.answer(text, reply_markup=markup)
    
    await query.answer()


# Noop handler for pagination display
@router.callback_query(F.data == 'noop', IsAdmin())
async def cb_noop(query: CallbackQuery):
    """No-op handler for pagination display."""
    await query.answer()
