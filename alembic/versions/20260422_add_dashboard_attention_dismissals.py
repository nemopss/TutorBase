"""Add dashboard attention dismissals

Revision ID: 20260422_add_dashboard_attention_dismissals
Revises: 20260421_add_learner_archive
Create Date: 2026-04-22 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260422_add_dashboard_attention_dismissals"
down_revision: Union[str, None] = "20260421_add_learner_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_attention_dismissals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("item_key", sa.String(length=255), nullable=False),
        sa.Column("dismissed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "item_type",
            "item_key",
            name="uq_dashboard_attention_dismissals_item",
        ),
    )
    op.create_index(
        "ix_dashboard_attention_dismissals_active",
        "dashboard_attention_dismissals",
        ["tenant_id", "item_type", "dismissed_until"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dashboard_attention_dismissals_tenant_id"),
        "dashboard_attention_dismissals",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dashboard_attention_dismissals_tenant_id"),
        table_name="dashboard_attention_dismissals",
    )
    op.drop_index(
        "ix_dashboard_attention_dismissals_active",
        table_name="dashboard_attention_dismissals",
    )
    op.drop_table("dashboard_attention_dismissals")
