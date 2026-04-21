from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.infrastructure.models import (
    NotificationAssignment,
    NotificationCategory,
    NotificationRule,
    NotificationTemplate,
)
from services.notification_bootstrap_service import ensure_recommended_notification_rules


async def test_ensure_recommended_notification_rules_creates_beta_defaults(
    db_session: AsyncSession,
) -> None:
    tenant_id = db_session.info["default_tenant_id"]
    category_by_key = {}
    for key, display_name in (
        ("lesson_confirmation", "Подтверждение"),
        ("lesson_reminder", "Напоминание"),
        ("homework", "Домашка"),
        ("package_renewal", "Продление"),
    ):
        category = NotificationCategory(key=key, display_name=display_name)
        db_session.add(category)
        category_by_key[key] = category
    await db_session.flush()

    for category_key, template_key in (
        ("lesson_confirmation", "lesson_confirmation_day_before_ru"),
        ("lesson_reminder", "lesson_reminder_soon_ru"),
        ("homework", "homework_before_lesson_ru"),
        ("package_renewal", "package_renewal_ru"),
    ):
        db_session.add(
            NotificationTemplate(
                tenant_id=None,
                category_id=category_by_key[category_key].id,
                key=template_key,
                name=template_key,
                locale="ru",
                body="Текст шаблона",
                version=1,
                system=True,
            )
        )
    await db_session.flush()

    created_count = await ensure_recommended_notification_rules(db_session, tenant_id)
    second_created_count = await ensure_recommended_notification_rules(db_session, tenant_id)

    assert created_count == 4
    assert second_created_count == 0

    result = await db_session.execute(
        select(NotificationRule.preset_key, NotificationRule.status).where(
            NotificationRule.tenant_id == tenant_id
        )
    )
    statuses = dict(result.all())
    assert statuses == {
        "lesson_confirmation_day_before": "active",
        "lesson_reminder_soon": "active",
        "homework_before_lesson": "paused",
        "package_renewal": "paused",
    }

    assignment_count = await db_session.scalar(
        select(func.count()).select_from(NotificationAssignment).where(NotificationAssignment.tenant_id == tenant_id)
    )
    assert assignment_count == 4
