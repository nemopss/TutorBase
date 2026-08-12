from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from notifications.application.delivery import NotificationDeliveryError
from notifications.domain.enums import CategoryKey, EventType
from notifications.infrastructure.models import (
    NotificationCategory,
    NotificationInstance,
    NotificationInstanceComponent,
    NotificationRule,
    NotificationTemplate,
)
from notifications.infrastructure.rendering import (
    SqlAlchemyNotificationRenderer,
    _instance_for_render_stmt,
)


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def one_or_none(self):
        return self._value


class FakeRenderSession:
    def __init__(self, instance, context_row):
        self.instance = instance
        self.context_row = context_row
        self.calls = []

    async def execute(self, statement):
        self.calls.append(statement)
        if len(self.calls) == 1:
            return FakeScalarResult(self.instance)
        return FakeScalarResult(self.context_row)


def _lesson_context_row():
    return SimpleNamespace(
        lesson_scheduled_at=datetime(2026, 4, 8, 17, 0, tzinfo=timezone.utc),
        homework_due_at=None,
        package_title="Вика март",
        timezone="Europe/Moscow",
        learner_name="Вика",
        teacher_name="Ксюша",
    )


def _instance(*, body: str = "Привет, {student_name}! Урок в {lesson_time}."):
    category = NotificationCategory(key="lesson_confirmation", display_name="Подтверждение")
    template = NotificationTemplate(key="lesson_confirmation", name="Подтверждение", body=body)
    rule = NotificationRule(
        id=1,
        category=category,
        template=template,
        name="Подтверждение",
        event_type="lesson",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -1, "local_time": "10:00"},
    )
    return NotificationInstance(
        id=101,
        tenant_id=1,
        rule=rule,
        category=category,
        event_type="lesson",
        event_id=617,
        event_key="lesson:617",
        recipient_type="learner",
        recipient_id=10,
        scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        status="processing",
        delivery_enabled=True,
        priority="normal",
        channel="telegram",
        dedupe_key="single|lesson_confirmation|x",
        manual_overrides={},
        explanation={},
    )


def test_instance_for_render_statement_filters_tenant_and_instance():
    stmt = _instance_for_render_stmt(tenant_id=1, instance_id=101)

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "notification_instances.tenant_id =" in compiled
    assert "notification_instances.id =" in compiled


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_renders_rule_template_with_lesson_context():
    session = FakeRenderSession(_instance(), _lesson_context_row())

    rendered = await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
        SimpleNamespace(
            instance_id=101,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
        )
    )

    assert rendered.text == "Привет, Вика! Урок в 20:00."
    assert rendered.parse_mode is None
    assert rendered.reply_markup_snapshot == {
        "inline_keyboard": [
            [
                {"text": "👍 Подтверждаю", "callback_data": "notif_confirm_lesson_101"},
            ],
            [
                {"text": "😔 Не смогу", "callback_data": "notif_decline_lesson_101"},
            ],
        ]
    }


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_renders_teacher_and_custom_note():
    instance = _instance(
        body="{teacher_name}: {student_name}, {custom_note}"
    )
    instance.manual_overrides = {"custom_note": "возьми тетрадь"}
    session = FakeRenderSession(instance, _lesson_context_row())

    rendered = await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
        SimpleNamespace(
            instance_id=101,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
        )
    )

    assert rendered.text == "Ксюша: Вика, возьми тетрадь"


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_renders_combined_instance_from_component_rules():
    confirmation = NotificationRule(
        id=1,
        template=NotificationTemplate(
            key="lesson_confirmation",
            name="Подтверждение",
            body="Привет, {student_name}! Всё в силе?",
        ),
    )
    homework = NotificationRule(
        id=2,
        template=NotificationTemplate(
            key="homework",
            name="Домашка",
            body="Не забудь домашку к {lesson_time}.",
        ),
    )
    instance = _instance()
    instance.rule = None
    instance.combination_key = "lesson_confirmation_homework"
    instance.components = [
        NotificationInstanceComponent(rule=confirmation),
        NotificationInstanceComponent(rule=homework),
    ]
    session = FakeRenderSession(instance, _lesson_context_row())

    rendered = await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
        SimpleNamespace(
            instance_id=101,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
        )
    )

    assert rendered.text == "Привет, Вика! Всё в силе?\n\nНе забудь домашку к 20:00."


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_strips_duplicate_greeting_from_combined_components():
    confirmation = NotificationRule(
        id=1,
        template=NotificationTemplate(
            key="lesson_confirmation",
            name="Подтверждение",
            body="Привет, {student_name}! Всё в силе?",
        ),
    )
    homework = NotificationRule(
        id=2,
        template=NotificationTemplate(
            key="homework",
            name="Домашка",
            body="Привет, {student_name}! Не забудь домашку к {lesson_time}.",
        ),
    )
    instance = _instance()
    instance.rule = None
    instance.combination_key = "lesson_confirmation_homework"
    instance.components = [
        NotificationInstanceComponent(rule=confirmation),
        NotificationInstanceComponent(rule=homework),
    ]
    session = FakeRenderSession(instance, _lesson_context_row())

    rendered = await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
        SimpleNamespace(
            instance_id=101,
            category=CategoryKey.LESSON_CONFIRMATION,
            event_type=EventType.LESSON,
        )
    )

    assert rendered.text == "Привет, Вика! Всё в силе?\n\nНе забудь домашку к 20:00."


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_renders_package_renewal_context_and_buttons():
    category = NotificationCategory(key="package_renewal", display_name="Продление пакета")
    template = NotificationTemplate(
        key="package_renewal",
        name="Продление пакета",
        body=(
            "Привет, {student_name}! Твой пакет занятий заканчивается {package_end}. "
            "Продолжаем?"
        ),
    )
    rule = NotificationRule(
        id=3,
        category=category,
        template=template,
        name="Продление пакета",
        event_type="package",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -14, "local_time": "10:00"},
    )
    instance = _instance()
    instance.rule = rule
    instance.category = category
    instance.event_type = "package"
    instance.event_id = 64
    instance.event_key = "package:64"
    session = FakeRenderSession(
        instance,
        SimpleNamespace(
            package_title="Пакет апрель",
            package_end=datetime(2026, 4, 30, 21, 0, tzinfo=timezone.utc),
            timezone="Europe/Moscow",
            learner_name="Вика",
            teacher_name="Ксюша",
        ),
    )

    rendered = await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
        SimpleNamespace(
            instance_id=101,
            category=CategoryKey.PACKAGE_RENEWAL,
            event_type=EventType.PACKAGE,
        )
    )

    assert rendered.text == "Привет, Вика! Твой пакет занятий заканчивается 01.05.2026. Продолжаем?"
    assert rendered.reply_markup_snapshot == {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Всё хорошо, продолжаем",
                    "callback_data": "notif_confirm_package_101",
                },
            ],
            [
                {
                    "text": "🤔 Нужно обсудить",
                    "callback_data": "notif_discuss_package_101",
                },
            ],
        ]
    }


@pytest.mark.asyncio
async def test_sqlalchemy_renderer_turns_template_errors_into_permanent_delivery_errors():
    session = FakeRenderSession(_instance(body="Привет, {unknown}.") , _lesson_context_row())

    with pytest.raises(NotificationDeliveryError) as exc_info:
        await SqlAlchemyNotificationRenderer(session, tenant_id=1).render(
            SimpleNamespace(
                instance_id=101,
                category=CategoryKey.LESSON_CONFIRMATION,
                event_type=EventType.LESSON,
            )
        )

    assert exc_info.value.error_code == "template_render_error"
    assert exc_info.value.retryable is False
