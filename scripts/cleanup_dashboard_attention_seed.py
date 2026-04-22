from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, or_, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.engine import async_session
from database.models import BotUser, DashboardAttentionDismissal, Learner, Lesson, LessonPackage
from notifications.infrastructure.models import NotificationInstance, NotificationResponse


async def cleanup_dashboard_attention_seed(*, tenant_id: int, label: str) -> None:
    learner_name_prefix = f"{label}%"
    package_title_prefix = f"{label}%"

    async with async_session() as session:
        learners = (
            await session.execute(
                select(Learner).where(
                    Learner.tenant_id == tenant_id,
                    Learner.display_name.like(learner_name_prefix),
                )
            )
        ).scalars().all()

        learner_ids = [learner.id for learner in learners]
        bot_user_ids = [learner.bot_user_id for learner in learners if learner.bot_user_id is not None]

        package_filters = [LessonPackage.title.like(package_title_prefix)]
        if learner_ids:
            package_filters.append(LessonPackage.learner_id.in_(learner_ids))
        packages = (
            await session.execute(
                select(LessonPackage).where(
                    LessonPackage.tenant_id == tenant_id,
                    or_(*package_filters),
                )
            )
        ).scalars().all()
        package_ids = [package.id for package in packages]

        if package_ids:
            lessons = (
                await session.execute(
                    select(Lesson).where(
                        Lesson.tenant_id == tenant_id,
                        Lesson.package_id.in_(package_ids),
                    )
                )
            ).scalars().all()
        else:
            lessons = []
        lesson_ids = [lesson.id for lesson in lessons]

        deleted_dismissals = 0
        if package_ids or lesson_ids:
            dismissal_clauses = []
            dismissal_clauses.extend(
                DashboardAttentionDismissal.item_key.like(f"package_ending_soon:{package_id}:%")
                for package_id in package_ids
            )
            dismissal_clauses.extend(
                DashboardAttentionDismissal.item_key.like(f"lesson_declined:%:{lesson_id}")
                for lesson_id in lesson_ids
            )
            result = await session.execute(
                delete(DashboardAttentionDismissal).where(
                    DashboardAttentionDismissal.tenant_id == tenant_id,
                    or_(*dismissal_clauses),
                )
            )
            deleted_dismissals = int(result.rowcount or 0)

        deleted_responses = 0
        if learner_ids or lesson_ids:
            response_filters = []
            if learner_ids:
                response_filters.append(NotificationResponse.learner_id.in_(learner_ids))
            if lesson_ids:
                response_filters.append(NotificationResponse.event_id.in_(lesson_ids))
            result = await session.execute(
                delete(NotificationResponse).where(
                    NotificationResponse.tenant_id == tenant_id,
                    or_(*response_filters),
                )
            )
            deleted_responses = int(result.rowcount or 0)

        deleted_instances = 0
        if learner_ids or lesson_ids:
            instance_filters = []
            if learner_ids:
                instance_filters.append(NotificationInstance.learner_id.in_(learner_ids))
            if lesson_ids:
                instance_filters.append(
                    (NotificationInstance.event_type == "lesson") & NotificationInstance.event_id.in_(lesson_ids)
                )
            result = await session.execute(
                delete(NotificationInstance).where(
                    NotificationInstance.tenant_id == tenant_id,
                    or_(*instance_filters),
                )
            )
            deleted_instances = int(result.rowcount or 0)

        deleted_learners = 0
        for learner in learners:
            await session.delete(learner)
            deleted_learners += 1

        deleted_bot_users = 0
        if bot_user_ids:
            result = await session.execute(
                delete(BotUser).where(BotUser.id.in_(bot_user_ids))
            )
            deleted_bot_users = int(result.rowcount or 0)

        await session.commit()

    print(f"Cleaned dashboard attention seed data for tenant_id={tenant_id}, label='{label}'")
    print(
        f"Deleted: learners={deleted_learners}, bot_users={deleted_bot_users}, "
        f"notification_instances={deleted_instances}, notification_responses={deleted_responses}, "
        f"dismissals={deleted_dismissals}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove dashboard attention seed data from the local dev DB.",
    )
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID that was used for seeding.")
    parser.add_argument(
        "--label",
        default="Dashboard QA",
        help="Prefix used by the seed script. Default matches the standard dashboard QA seed.",
    )
    args = parser.parse_args()
    asyncio.run(cleanup_dashboard_attention_seed(tenant_id=args.tenant_id, label=args.label))


if __name__ == "__main__":
    main()
