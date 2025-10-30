import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant
from database import crud
from services.reminders import ReminderScheduler
from services.reminder_definitions import (
    REMINDER_TYPE_LESSON_CONFIRM,
    REMINDER_TYPE_LESSON_DAY_BEFORE,
    REMINDER_TYPE_PAYMENT_WEEK,
    REMINDER_TYPE_PAYMENT_DAY,
    REMINDER_TYPE_HOMEWORK,
    REMINDER_TYPE_PACKAGE_RENEWAL,
)
from tests import factories
from utils.scheduling import MOSCOW_TZ


@pytest.fixture
def mock_bot():
    """Fixture for a mocked Aiogram Bot instance."""
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def reminder_scheduler(mock_bot):
    """Fixture for ReminderScheduler with a mocked bot."""
    return ReminderScheduler(bot=mock_bot)


@pytest.mark.asyncio
async def test_process_instance_success(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    """Tests successful processing and sending of a reminder instance."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(db_session, package=package)
    rule = await factories.create_reminder_rule(
        db_session, package=package, lesson=lesson, reminder_type=REMINDER_TYPE_LESSON_CONFIRM
    )
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        lesson=lesson,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        status="scheduled",
        payload={"schedule_label": "Today 10:00"},
    )
    await db_session.flush()

    learner.bot_user.chat_id = 12345
    await db_session.flush()

    mock_bot.send_message.return_value = MagicMock()

    await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    assert mock_bot.send_message.call_count == 2
    assert mock_bot.send_message.call_args_list[0][0][0] == 12345
    assert "Напоминаю о занятии" in mock_bot.send_message.call_args_list[0][0][1]

    refreshed_instance = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed_instance.status == "sent"
    assert refreshed_instance.last_notified_at is not None
    assert refreshed_instance.active is False


@pytest.mark.asyncio
async def test_process_instance_notifications_disabled(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    """Tests that reminder is skipped if learner notifications are disabled."""
    learner = await factories.create_learner(db_session, display_name="Test Learner", notifications_enabled=False)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    mock_bot.send_message.assert_not_called()
    refreshed_instance = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed_instance.status == "skipped"
    assert refreshed_instance.active is False
    assert "Notifications disabled" in refreshed_instance.comment


@pytest.mark.asyncio
async def test_process_instance_telegram_forbidden_error(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    """Tests handling of TelegramForbiddenError during message sending."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner.bot_user.chat_id = 12345
    await db_session.flush()

    mock_bot.send_message.side_effect = TelegramForbiddenError(method="sendMessage", message="Bot was blocked by the user")

    with patch("services.reminders.config.ADMINS", [111, 222]):
        await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    assert mock_bot.send_message.call_count == 3
    refreshed_instance = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed_instance.status == "failed"
    assert refreshed_instance.active is False
    assert "TelegramForbiddenError" in refreshed_instance.comment


@pytest.mark.asyncio
async def test_process_instance_telegram_bad_request_error(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    """Tests handling of TelegramBadRequest during message sending."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner.bot_user.chat_id = 12345
    await db_session.flush()

    mock_bot.send_message.side_effect = TelegramBadRequest(method="sendMessage", message="Invalid chat ID")

    with patch("services.reminders.config.ADMINS", [111, 222]):
        await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    assert mock_bot.send_message.call_count == 3
    refreshed_instance = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed_instance.status == "failed"
    assert refreshed_instance.active is False
    assert "TelegramBadRequest" in refreshed_instance.comment


@pytest.mark.asyncio
async def test_process_instance_generic_exception(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    """Tests handling of a generic exception during message sending (should retry)."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner.bot_user.chat_id = 12345
    await db_session.flush()

    mock_bot.send_message.side_effect = ConnectionError("Network unreachable")

    await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    assert mock_bot.send_message.call_count == 1
    refreshed_instance = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed_instance.status == "pending"
    assert refreshed_instance.active is True
    assert "Temporary failure" in refreshed_instance.comment

@pytest.mark.asyncio
async def test_process_instance_no_valid_chat_identifier(
    db_session, reminder_scheduler, mock_bot, current_tenant: CurrentTenant
):
    """
    Если задан невалидный chat_identifier, сервис делает одну попытку отправки пользователю
    (на этот невалидный идентификатор), получает Forbidden и помечает инстанс как failed.
    Дополнительные вызовы send_message возможны из-за уведомлений админов — их не фиксируем.
    """
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)

    invalid_id = "invalid_username"
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        chat_identifier=invalid_id,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    mock_bot.send_message.side_effect = TelegramForbiddenError(
        method="sendMessage", message="Blocked"
    )

    await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    refreshed = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed is not None
    assert refreshed.status == "failed"

    assert mock_bot.send_message.call_count >= 1

    first_call = mock_bot.send_message.call_args_list[0]
    first_target = first_call.kwargs.get(
        "chat_id",
        first_call.args[0] if first_call.args else None,
    )
    assert first_target == invalid_id

    if len(mock_bot.send_message.call_args_list) > 1:
        other_targets = []
        for ca in mock_bot.send_message.call_args_list[1:]:
            other_targets.append(ca.kwargs.get("chat_id", ca.args[0] if ca.args else None))
        assert any(t != invalid_id for t in other_targets)


@pytest.mark.asyncio
async def test_process_instance_empty_message_text(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="unknown_type")
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner.bot_user.chat_id = 12345
    await db_session.flush()

    with patch("services.reminders.config.LOGS_CHAT_ID", 999), \
         patch("services.reminders.config.REMINDER_NOTIFY_USERNAME", "test_admin"):
        await reminder_scheduler._process_instance(db_session, instance, datetime.now(timezone.utc))

    assert mock_bot.send_message.call_count == 2
    refreshed = await crud.get_reminder_instance(db_session, current_tenant, instance.id)
    assert refreshed.status == "sent"
    assert refreshed.active is False


@pytest.mark.asyncio
async def test_process_instances_with_multiple_instances(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock, current_tenant: CurrentTenant
):
    learner1 = await factories.create_learner(db_session, display_name="Learner 1")
    learner2 = await factories.create_learner(db_session, display_name="Learner 2")
    package1 = await factories.create_package(db_session, learner=learner1)
    package2 = await factories.create_package(db_session, learner=learner2)
    rule1 = await factories.create_reminder_rule(db_session, package=package1)
    rule2 = await factories.create_reminder_rule(db_session, package=package2)

    instance1 = await factories.create_reminder_instance(
        db_session, rule=rule1, package=package1, learner=learner1,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    instance2 = await factories.create_reminder_instance(
        db_session, rule=rule2, package=package2, learner=learner2,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner1.bot_user.chat_id = 111
    learner2.bot_user.chat_id = 222
    await db_session.flush()

    with patch("services.reminders.config.LOGS_CHAT_ID", 999), \
         patch("services.reminders.config.ADMINS", [1001, 1002]), \
         patch("services.reminders.config.REMINDER_NOTIFY_USERNAME", "test_admin"):

        def send_message_side_effect(chat_id, *args, **kwargs):
            if chat_id == 222:
                raise TelegramForbiddenError(method="sendMessage", message="Blocked")
            return MagicMock()

        mock_bot.send_message.side_effect = send_message_side_effect

        await reminder_scheduler._process_instances(db_session, datetime.now(timezone.utc))

    r1 = await crud.get_reminder_instance(db_session, current_tenant, instance1.id)
    r2 = await crud.get_reminder_instance(db_session, current_tenant, instance2.id)
    assert r1.status == "sent"
    assert r2.status == "failed"
    assert r2.active is False


@pytest.mark.asyncio
async def test_process_instances_exception_in_processing_instance(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock
):
    learner1 = await factories.create_learner(db_session, display_name="Learner 1")
    learner2 = await factories.create_learner(db_session, display_name="Learner 2")
    package1 = await factories.create_package(db_session, learner=learner1)
    package2 = await factories.create_package(db_session, learner=learner2)
    rule1 = await factories.create_reminder_rule(db_session, package=package1)
    rule2 = await factories.create_reminder_rule(db_session, package=package2)

    instance1 = await factories.create_reminder_instance(
        db_session,
        rule=rule1,
        package=package1,
        learner=learner1,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    instance2 = await factories.create_reminder_instance(
        db_session,
        rule=rule2,
        package=package2,
        learner=learner2,
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    await db_session.flush()

    learner1.bot_user.chat_id = 111
    learner2.bot_user.chat_id = 222
    await db_session.flush()

    with patch.object(reminder_scheduler, "_process_instance", side_effect=[Exception("Test Error"), None]) as mocked:
        await reminder_scheduler._process_instances(db_session, datetime.now(timezone.utc))

        assert mocked.call_count == 2

        second_call_args = mocked.call_args_list[1].args
        assert second_call_args[1].id == instance2.id


@pytest.mark.asyncio
async def test_scheduler_start_stop(reminder_scheduler: ReminderScheduler):
    """Tests starting and stopping the scheduler."""
    await reminder_scheduler.start()
    assert reminder_scheduler._task is not None
    assert not reminder_scheduler._stop_event.is_set()

    old_task = reminder_scheduler._task
    await reminder_scheduler.start()
    assert reminder_scheduler._task == old_task

    await reminder_scheduler.stop()
    assert reminder_scheduler._task is None
    assert reminder_scheduler._stop_event.is_set()

    await reminder_scheduler.stop()
    assert reminder_scheduler._task is None


@pytest.mark.asyncio
async def test_scheduler_runner_exception_handling(reminder_scheduler: ReminderScheduler):
    """Tests that exceptions in _tick are caught and logged, and the runner continues."""
    with patch("logging.exception") as mock_logging_exception:
        with patch.object(reminder_scheduler, "_tick", side_effect=Exception("Test Tick Error")):
            await reminder_scheduler.start()
            await asyncio.sleep(0.1)
            await reminder_scheduler.stop()

            mock_logging_exception.assert_called()


@pytest.mark.asyncio
async def test_describe_instance_kind(db_session: AsyncSession, reminder_scheduler: ReminderScheduler):
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)

    cases = [
        (REMINDER_TYPE_LESSON_CONFIRM, "еженедельное"),
        (REMINDER_TYPE_LESSON_DAY_BEFORE, "подтверждение за день"),
        ("unknown_type", "unknown_type"),
    ]
    for r_type, expected in cases:
        rule = await factories.create_reminder_rule(db_session, package=package, reminder_type=r_type)
        instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
        await db_session.flush()
        assert reminder_scheduler._describe_instance_kind(instance) == expected


@pytest.mark.asyncio
async def test_instance_student_name(db_session: AsyncSession, reminder_scheduler: ReminderScheduler):
    """Tests _instance_student_name for various scenarios."""
    learner = await factories.create_learner(db_session, display_name="Learner Name")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)

    instance1 = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()
    assert reminder_scheduler._instance_student_name(instance1) == "Learner Name"

    instance2 = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, payload={"student_name": "Payload Name"}
    )
    await db_session.flush()
    assert reminder_scheduler._instance_student_name(instance2) == "Payload Name"


@pytest.mark.asyncio
async def test_resolve_instance_target(db_session: AsyncSession, reminder_scheduler: ReminderScheduler):
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)

    learner.bot_user.chat_id = 12345
    instance1 = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()
    target, display = reminder_scheduler._resolve_instance_target(instance1)
    assert target == 12345
    assert display == "12345"

    instance2 = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, chat_identifier="67890"
    )
    await db_session.flush()
    target, display = reminder_scheduler._resolve_instance_target(instance2)
    assert target == 67890
    assert display == "67890"

    instance3 = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, chat_identifier="Custom Label|98765"
    )
    await db_session.flush()
    target, display = reminder_scheduler._resolve_instance_target(instance3)
    assert target == 98765
    assert display == "Custom Label"



@pytest.mark.asyncio
async def test_build_instance_schedule(db_session: AsyncSession, reminder_scheduler: ReminderScheduler):
    """Tests _build_instance_schedule for various scenarios."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    lesson = await factories.create_lesson(
        db_session, package=package, scheduled_at=datetime(2024, 1, 1, 10, 0, tzinfo=MOSCOW_TZ)
    )
    rule = await factories.create_reminder_rule(db_session, package=package, lesson=lesson)

    instance1 = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner, lesson=lesson)
    await db_session.flush()
    schedule_label = reminder_scheduler._build_instance_schedule(instance1)
    assert "2024-01-01 10:00 MSK" in schedule_label

    instance2 = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, payload={"schedule_label": "Custom Schedule"}
    )
    await db_session.flush()
    schedule_label = reminder_scheduler._build_instance_schedule(instance2)
    assert schedule_label == "Custom Schedule"

    instance3 = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, scheduled_at=datetime(2024, 2, 1, 11, 0, tzinfo=MOSCOW_TZ)
    )
    await db_session.flush()
    schedule_label = reminder_scheduler._build_instance_schedule(instance3)
    assert "2024-02-01 11:00 MSK" in schedule_label


@pytest.mark.asyncio
async def test_format_with_timezone(reminder_scheduler: ReminderScheduler):
    """Tests _format_with_timezone for various scenarios."""
    dt_utc = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt_naive = datetime(2024, 1, 1, 12, 0)

    formatted = reminder_scheduler._format_with_timezone(dt_utc, "Europe/London")
    assert "2024-01-01 12:00 GMT" in formatted

    formatted_invalid_tz = reminder_scheduler._format_with_timezone(dt_utc, "Invalid/Timezone")
    assert "2024-01-01 15:00 MSK" in formatted_invalid_tz

    formatted_naive = reminder_scheduler._format_with_timezone(dt_naive, "Europe/Moscow")
    assert "2024-01-01 15:00 MSK" in formatted_naive


@pytest.mark.asyncio
async def test_build_instance_message_lesson_confirm(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for LESSON_CONFIRM type."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type=REMINDER_TYPE_LESSON_CONFIRM)
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Today 10:00")
    assert "Напоминаю о занятии" in message
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) == 2


@pytest.mark.asyncio
async def test_build_instance_message_lesson_day_before(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for LESSON_DAY_BEFORE type."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type=REMINDER_TYPE_LESSON_DAY_BEFORE)
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Tomorrow 10:00")
    assert "у тебя завтра занятие" in message
    assert "Всё в силе" in message
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) == 2


@pytest.mark.asyncio
async def test_build_instance_message_payment_week(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for PAYMENT_WEEK type."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="payment_week")
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Schedule")
    assert "через неделю заканчивается" in message
    assert "Продолжаем в том же темпе" in message
    assert keyboard is not None  # Now has buttons
    assert len(keyboard.inline_keyboard) == 2  # Confirm and Decline buttons


@pytest.mark.asyncio
async def test_build_instance_message_payment_day(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for PAYMENT_DAY type."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="payment_day")
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Schedule")
    assert "Завтра истекает срок" in message
    assert "оплаченного пакета" in message
    assert keyboard is not None  # Now has buttons
    assert len(keyboard.inline_keyboard) == 2  # Confirm and Decline buttons


@pytest.mark.asyncio
async def test_build_instance_message_homework(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for HOMEWORK type."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="homework")
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Schedule")
    assert "Не забудь выполнить и отправить домашку" in message
    assert keyboard is None


@pytest.mark.asyncio
async def test_build_instance_message_package_renewal(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message for PACKAGE_RENEWAL type."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="package_renewal")
    instance = await factories.create_reminder_instance(
        db_session, rule=rule, package=package, learner=learner, payload={"package_end": "2024-12-31"}
    )
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Schedule")
    assert "2024-12-31" in message
    assert keyboard is None


@pytest.mark.asyncio
async def test_build_instance_message_fallback(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler
):
    """Tests _build_instance_message fallback to generic message."""
    learner = await factories.create_learner(db_session)
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type="unrecognized_type")
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    message, keyboard = reminder_scheduler._build_instance_message(instance, "Generic Schedule")
    assert "Напоминаю" in message
    assert "Generic Schedule" in message
    assert keyboard is None


@pytest.mark.asyncio
async def test_log_instance_sent_success(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock
):
    """Tests successful logging of a sent reminder instance."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package, reminder_type=REMINDER_TYPE_LESSON_CONFIRM)
    instance = await factories.create_reminder_instance(
        db_session,
        rule=rule,
        package=package,
        learner=learner,
        payload={"lead_minutes": 60},
    )
    await db_session.flush()

    with patch("services.reminders.config.LOGS_CHAT_ID", 999), \
         patch("services.reminders.config.REMINDER_NOTIFY_USERNAME", "test_admin"):
        await reminder_scheduler._log_instance_sent(instance, "Today 10:00")
        mock_bot.send_message.assert_called_once()
        assert mock_bot.send_message.call_args[0][0] == 999
        text = mock_bot.send_message.call_args[0][1]
        assert "Test Learner" in text
        assert "Today 10:00" in text
        assert "60" in text
        assert "test_admin" in text


@pytest.mark.asyncio
async def test_log_instance_sent_failure(
    db_session: AsyncSession, reminder_scheduler: ReminderScheduler, mock_bot: AsyncMock
):
    """Tests handling of exceptions during logging of sent reminder instance."""
    learner = await factories.create_learner(db_session, display_name="Test Learner")
    package = await factories.create_package(db_session, learner=learner)
    rule = await factories.create_reminder_rule(db_session, package=package)
    instance = await factories.create_reminder_instance(db_session, rule=rule, package=package, learner=learner)
    await db_session.flush()

    mock_bot.send_message.side_effect = Exception("Log send failed")

    with patch("logging.error") as mock_logging_error:
        await reminder_scheduler._log_instance_sent(instance, "Schedule")
        mock_logging_error.assert_called_once()