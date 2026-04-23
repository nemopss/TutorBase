"""Add notification activity acknowledgements

Revision ID: 20260423_add_notification_activity_acknowledgements
Revises: 20260422_add_dashboard_attention_dismissals
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260423_add_notification_activity_acknowledgements"
down_revision: Union[str, None] = "20260422_add_dashboard_attention_dismissals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_activity_acknowledgements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(length=64), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "activity_type",
            "activity_id",
            name="uq_notification_activity_acknowledgements_item",
        ),
    )
    op.create_index(
        "ix_notification_activity_acknowledgements_lookup",
        "notification_activity_acknowledgements",
        ["tenant_id", "activity_type", "acknowledged_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_activity_acknowledgements_tenant_id"),
        "notification_activity_acknowledgements",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_notification_activity_acknowledgements_tenant_id"),
        table_name="notification_activity_acknowledgements",
    )
    op.drop_index(
        "ix_notification_activity_acknowledgements_lookup",
        table_name="notification_activity_acknowledgements",
    )
    op.drop_table("notification_activity_acknowledgements")
