"""Add explicit package modes and harden notification outbox

Revision ID: 20260730_package_modes_outbox
Revises: 20260518_start_plan_limit_five
Create Date: 2026-07-30 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260730_package_modes_outbox"
down_revision: Union[str, None] = "20260518_start_plan_limit_five"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lesson_packages",
        sa.Column("schedule_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "lesson_packages",
        sa.Column("renewal_enabled", sa.Boolean(), nullable=True),
    )
    op.execute(
        """
        UPDATE lesson_packages
        SET schedule_mode = CASE
                WHEN package_type = 'one_off' THEN 'one_off'
                WHEN template_id IS NOT NULL OR end_date IS NOT NULL THEN 'fixed'
                ELSE 'flexible'
            END,
            renewal_enabled = CASE
                WHEN package_type = 'package'
                     AND (template_id IS NOT NULL OR end_date IS NOT NULL)
                THEN TRUE
                ELSE FALSE
            END
        """
    )
    op.alter_column(
        "lesson_packages",
        "schedule_mode",
        nullable=False,
        server_default="flexible",
    )
    op.alter_column(
        "lesson_packages",
        "renewal_enabled",
        nullable=False,
        server_default=sa.false(),
    )
    op.create_index(
        "ix_lesson_packages_tenant_schedule_mode",
        "lesson_packages",
        ["tenant_id", "schedule_mode"],
        unique=False,
    )

    op.add_column(
        "notification_jobs",
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "notification_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "notification_jobs",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notification_jobs_tenant_available",
        "notification_jobs",
        ["tenant_id", "status", "available_at"],
        unique=False,
    )
    op.create_index(
        "uq_notification_jobs_active_dedupe",
        "notification_jobs",
        ["tenant_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text(
            "dedupe_key IS NOT NULL AND status = 'queued'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notification_jobs_active_dedupe",
        table_name="notification_jobs",
    )
    op.drop_index(
        "ix_notification_jobs_tenant_available",
        table_name="notification_jobs",
    )
    op.drop_column("notification_jobs", "available_at")
    op.drop_column("notification_jobs", "attempt_count")
    op.drop_column("notification_jobs", "dedupe_key")

    op.drop_index(
        "ix_lesson_packages_tenant_schedule_mode",
        table_name="lesson_packages",
    )
    op.drop_column("lesson_packages", "renewal_enabled")
    op.drop_column("lesson_packages", "schedule_mode")
