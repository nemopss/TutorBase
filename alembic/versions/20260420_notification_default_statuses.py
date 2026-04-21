"""Set beta-ready default notification rule statuses

Revision ID: 20260420_notification_default_statuses
Revises: 20260419_platform_broadcasts
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260420_notification_default_statuses"
down_revision: Union[str, None] = "20260419_platform_broadcasts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE notification_rules_v2
        SET
            status = 'active',
            activated_at = COALESCE(activated_at, CURRENT_TIMESTAMP),
            paused_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE preset_key IN ('lesson_confirmation_day_before', 'lesson_reminder_soon')
          AND status = 'draft'
        """
    )
    op.execute(
        """
        UPDATE notification_rules_v2
        SET
            status = 'paused',
            paused_at = COALESCE(paused_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE preset_key IN ('homework_before_lesson', 'package_renewal')
          AND status = 'draft'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE notification_rules_v2
        SET
            status = 'draft',
            activated_at = NULL,
            paused_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE preset_key IN (
            'lesson_confirmation_day_before',
            'lesson_reminder_soon',
            'homework_before_lesson',
            'package_renewal'
        )
          AND created_by_user_id IS NULL
          AND status IN ('active', 'paused')
        """
    )
