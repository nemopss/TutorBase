"""Bootstrap recommended notification rules for new tutor tenants."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import _utc_now
from notifications.infrastructure.models import (
    NotificationAssignment,
    NotificationCategory,
    NotificationRule,
    NotificationTemplate,
)


@dataclass(frozen=True)
class RecommendedRuleSeed:
    preset_key: str
    category_key: str
    template_key: str
    name: str
    description: str
    event_type: str
    trigger_type: str
    trigger_config: dict[str, object]
    status: str
    combine_policy_key: str | None = None


RECOMMENDED_RULE_SEEDS: tuple[RecommendedRuleSeed, ...] = (
    RecommendedRuleSeed(
        preset_key="lesson_confirmation_day_before",
        category_key="lesson_confirmation",
        template_key="lesson_confirmation_day_before_ru",
        name="Подтверждение урока за день",
        description="Базовый сценарий: спросить ученика за день до урока.",
        event_type="lesson",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -1, "local_time": "10:00", "event_field": "starts_at"},
        status="active",
        combine_policy_key="lesson_confirmation_homework",
    ),
    RecommendedRuleSeed(
        preset_key="lesson_reminder_soon",
        category_key="lesson_reminder",
        template_key="lesson_reminder_soon_ru",
        name="Напоминание перед уроком",
        description="Базовый сценарий: мягкое напоминание за час до урока.",
        event_type="lesson",
        trigger_type="relative_offset",
        trigger_config={"minutes": -60, "event_field": "starts_at"},
        status="active",
    ),
    RecommendedRuleSeed(
        preset_key="homework_before_lesson",
        category_key="homework",
        template_key="homework_before_lesson_ru",
        name="Домашка к уроку",
        description="Дополнительный сценарий: напомнить о домашке за день до урока.",
        event_type="lesson",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -1, "local_time": "10:00", "event_field": "starts_at"},
        status="paused",
        combine_policy_key="lesson_confirmation_homework",
    ),
    RecommendedRuleSeed(
        preset_key="package_renewal",
        category_key="package_renewal",
        template_key="package_renewal_ru",
        name="Продление пакета",
        description="Дополнительный сценарий: напомнить о продлении пакета за 14 дней.",
        event_type="package",
        trigger_type="day_offset_at_time",
        trigger_config={"days": -14, "local_time": "10:00", "event_field": "starts_at"},
        status="paused",
    ),
)


async def ensure_recommended_notification_rules(session: AsyncSession, tenant_id: int) -> int:
    """Create missing recommended notification rules for a tenant.

    The function is idempotent and leaves existing preset rules untouched.
    """
    preset_keys = tuple(seed.preset_key for seed in RECOMMENDED_RULE_SEEDS)
    existing_result = await session.execute(
        select(NotificationRule.preset_key).where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.preset_key.in_(preset_keys),
        )
    )
    existing_keys = {key for key in existing_result.scalars() if key is not None}
    missing_seeds = tuple(seed for seed in RECOMMENDED_RULE_SEEDS if seed.preset_key not in existing_keys)
    if not missing_seeds:
        return 0

    category_keys = {seed.category_key for seed in missing_seeds}
    category_result = await session.execute(
        select(NotificationCategory).where(NotificationCategory.key.in_(category_keys))
    )
    categories_by_key = {category.key: category for category in category_result.scalars()}

    template_keys = {seed.template_key for seed in missing_seeds}
    template_result = await session.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.tenant_id.is_(None),
            NotificationTemplate.key.in_(template_keys),
            NotificationTemplate.locale == "ru",
            NotificationTemplate.version == 1,
            NotificationTemplate.archived_at.is_(None),
        )
    )
    templates_by_key = {template.key: template for template in template_result.scalars()}

    created_count = 0
    now = _utc_now()
    for seed in missing_seeds:
        category = categories_by_key.get(seed.category_key)
        template = templates_by_key.get(seed.template_key)
        if category is None or template is None:
            continue

        rule = NotificationRule(
            tenant_id=tenant_id,
            preset_key=seed.preset_key,
            category_id=category.id,
            template_id=template.id,
            inline_template_body=None,
            inline_template_format="plain_text",
            name=seed.name,
            description=seed.description,
            event_type=seed.event_type,
            trigger_type=seed.trigger_type,
            trigger_config=seed.trigger_config,
            priority="normal",
            status=seed.status,
            combine_policy_key=seed.combine_policy_key,
            delivery_channel="telegram",
            cap_mode="warn_only",
            quiet_hours_mode="shift",
            bypass_quiet_hours=False,
            created_by_user_id=None,
            activated_at=now if seed.status == "active" else None,
            paused_at=now if seed.status == "paused" else None,
            archived_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add(rule)
        await session.flush()
        session.add(
            NotificationAssignment(
                tenant_id=tenant_id,
                rule_id=rule.id,
                scope_type="all_learners",
                scope_id=None,
                is_exclusion=False,
                created_at=now,
                updated_at=now,
            )
        )
        created_count += 1

    return created_count
