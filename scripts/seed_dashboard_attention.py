from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.engine import async_session
from notifications.domain.enums import CategoryKey, EventType, InstanceStatus, Priority
from notifications.infrastructure.models import (
    NotificationCategory,
    NotificationDeliveryAttempt,
    NotificationInstance,
    NotificationResponse,
)
from tests import factories


MSK = ZoneInfo("Europe/Moscow")


async def _get_or_create_category(
    session,
    *,
    key: CategoryKey,
    display_name: str,
) -> NotificationCategory:
    result = await session.execute(
        select(NotificationCategory).where(NotificationCategory.key == key.value)
    )
    category = result.scalar_one_or_none()
    if category is not None:
        return category

    now = datetime.now(timezone.utc)
    category = NotificationCategory(
        key=key.value,
        display_name=display_name,
        system=True,
        default_priority=Priority.NORMAL.value,
        default_counts_towards_daily_cap=True,
        default_can_bypass_quiet_hours=False,
        created_at=now,
        updated_at=now,
    )
    session.add(category)
    await session.flush()
    return category


def _fmt_msk(value: datetime) -> str:
    return value.astimezone(MSK).strftime("%d.%m.%Y %H:%M")


async def seed_dashboard_attention(*, tenant_id: int, label: str) -> None:
    now = datetime.now(timezone.utc)
    suffix = now.strftime("%Y%m%d-%H%M%S")
    prefix = f"{label} {suffix}"

    async with async_session() as session:
        reminder_category = await _get_or_create_category(
            session,
            key=CategoryKey.LESSON_REMINDER,
            display_name="Напоминание об уроке",
        )
        confirmation_category = await _get_or_create_category(
            session,
            key=CategoryKey.LESSON_CONFIRMATION,
            display_name="Подтверждение урока",
        )

        # Packages attention: active package with the last future non-cancelled lesson in <= 3 days.
        package_learner = await factories.create_learner(
            session,
            tenant_id=tenant_id,
            display_name=f"{prefix} / Package learner",
        )
        await session.flush()
        package_bundle = await factories.create_package(
            session,
            tenant_id=tenant_id,
            learner=package_learner,
            status="active",
            title=f"{prefix} / Package ending soon",
        )
        await session.flush()
        package_lesson_at = now + timedelta(days=2, hours=1)
        package_lesson = await factories.create_lesson(
            session,
            tenant_id=tenant_id,
            package=package_bundle,
            scheduled_at=package_lesson_at,
            status="scheduled",
            duration_minutes=60,
        )
        await session.flush()

        # Notifications attention: failed notification instance with a failed attempt.
        failed_learner = await factories.create_learner(
            session,
            tenant_id=tenant_id,
            display_name=f"{prefix} / Failed notification learner",
        )
        await session.flush()
        failed_package = await factories.create_package(
            session,
            tenant_id=tenant_id,
            learner=failed_learner,
            status="active",
            title=f"{prefix} / Failed notification package",
        )
        await session.flush()
        failed_lesson_at = now + timedelta(days=5, hours=3)
        failed_lesson = await factories.create_lesson(
            session,
            tenant_id=tenant_id,
            package=failed_package,
            scheduled_at=failed_lesson_at,
            status="scheduled",
            duration_minutes=60,
        )
        await session.flush()
        failed_instance = NotificationInstance(
            tenant_id=tenant_id,
            rule_id=None,
            category_id=reminder_category.id,
            event_type=EventType.LESSON.value,
            event_id=failed_lesson.id,
            event_key=f"lesson:{failed_lesson.id}",
            recipient_type="learner",
            recipient_id=failed_learner.id,
            learner_id=failed_learner.id,
            scheduled_for=failed_lesson_at,
            effective_scheduled_for=failed_lesson_at,
            status=InstanceStatus.FAILED.value,
            status_reason="manual_dashboard_seed",
            delivery_enabled=False,
            priority=Priority.NORMAL.value,
            channel="telegram",
            dedupe_key=f"manual_seed|dashboard_attention|failed_notification|{failed_lesson.id}",
            explanation={"reason": "manual_dashboard_seed"},
            created_at=now,
            updated_at=now,
        )
        session.add(failed_instance)
        await session.flush()
        failed_attempt = NotificationDeliveryAttempt(
            tenant_id=tenant_id,
            notification_instance_id=failed_instance.id,
            attempt_no=1,
            status=InstanceStatus.FAILED.value,
            channel="telegram",
            provider="telegram",
            error_code="MANUAL_SEED",
            error_message=f"{prefix}: forced failed delivery for dashboard QA",
            started_at=now,
            finished_at=now,
            created_at=now,
        )
        session.add(failed_attempt)

        # Lessons attention: teacher alert produced by a declined response for a future lesson.
        declined_learner = await factories.create_learner(
            session,
            tenant_id=tenant_id,
            display_name=f"{prefix} / Declined lesson learner",
        )
        await session.flush()
        declined_package = await factories.create_package(
            session,
            tenant_id=tenant_id,
            learner=declined_learner,
            status="active",
            title=f"{prefix} / Declined lesson package",
        )
        await session.flush()
        declined_lesson_at = now + timedelta(days=5, hours=5)
        declined_lesson = await factories.create_lesson(
            session,
            tenant_id=tenant_id,
            package=declined_package,
            scheduled_at=declined_lesson_at,
            status="scheduled",
            duration_minutes=60,
        )
        await session.flush()
        declined_instance = NotificationInstance(
            tenant_id=tenant_id,
            rule_id=None,
            category_id=confirmation_category.id,
            event_type=EventType.LESSON.value,
            event_id=declined_lesson.id,
            event_key=f"lesson:{declined_lesson.id}",
            recipient_type="learner",
            recipient_id=declined_learner.id,
            learner_id=declined_learner.id,
            scheduled_for=declined_lesson_at - timedelta(days=1),
            effective_scheduled_for=declined_lesson_at - timedelta(days=1),
            status=InstanceStatus.SENT.value,
            delivery_enabled=False,
            priority=Priority.NORMAL.value,
            channel="telegram",
            dedupe_key=f"manual_seed|dashboard_attention|lesson_declined|{declined_lesson.id}",
            explanation={"reason": "manual_dashboard_seed"},
            created_at=now,
            updated_at=now,
        )
        session.add(declined_instance)
        await session.flush()
        declined_response = NotificationResponse(
            tenant_id=tenant_id,
            notification_instance_id=declined_instance.id,
            event_type=EventType.LESSON.value,
            event_id=declined_lesson.id,
            recipient_type="learner",
            recipient_id=declined_learner.id,
            learner_id=declined_learner.id,
            action_key="decline_lesson",
            response_value="declined",
            response_text=f"{prefix}: manual decline for dashboard QA",
            response_metadata={},
            created_at=now,
        )
        session.add(declined_response)

        await session.commit()

    print(f"Seeded dashboard attention fixtures for tenant_id={tenant_id}")
    print()
    print("Expected dashboard items:")
    print(
        f"- Packages: {package_learner.display_name} · {package_bundle.title} · last lesson {_fmt_msk(package_lesson_at)}"
    )
    print(
        f"- Notifications: {failed_learner.display_name} · forced failed delivery · lesson {_fmt_msk(failed_lesson_at)}"
    )
    print(
        f"- Lessons: {declined_learner.display_name} · declined future lesson {_fmt_msk(declined_lesson_at)}"
    )
    print()
    print("Created IDs:")
    print(
        f"  package_case: learner={package_learner.id}, package={package_bundle.id}, lesson={package_lesson.id}"
    )
    print(
        f"  notification_case: learner={failed_learner.id}, package={failed_package.id}, lesson={failed_lesson.id}, instance={failed_instance.id}"
    )
    print(
        f"  lesson_case: learner={declined_learner.id}, package={declined_package.id}, lesson={declined_lesson.id}, instance={declined_instance.id}, response={declined_response.id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed local dev DB with deterministic Dashboard 'Requires attention' fixtures.",
    )
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID that your current dev user is viewing.")
    parser.add_argument(
        "--label",
        default="Dashboard QA",
        help="Prefix used in learner/package names for easier identification.",
    )
    args = parser.parse_args()
    asyncio.run(seed_dashboard_attention(tenant_id=args.tenant_id, label=args.label))


if __name__ == "__main__":
    main()
