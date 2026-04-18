"""Add tenant SaaS access state

Revision ID: 20260418_tenant_access
Revises: 20260418_invite_tokens_learner_id
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260418_tenant_access"
down_revision: Union[str, None] = "20260418_invite_tokens_learner_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("access_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_access_tenant_id", "tenant_access", ["tenant_id"])
    op.create_index("ix_tenant_access_status_until", "tenant_access", ["status", "access_until"])

    op.create_table(
        "tenant_access_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_access_events_tenant_id", "tenant_access_events", ["tenant_id"])
    op.create_index("ix_tenant_access_events_actor_user_id", "tenant_access_events", ["actor_user_id"])

    op.execute(
        """
        INSERT INTO tenant_access (
            tenant_id,
            status,
            notes,
            created_at,
            updated_at
        )
        SELECT
            tenants.id,
            'lifetime',
            'Backfilled during tenant access migration',
            now(),
            now()
        FROM tenants
        WHERE NOT EXISTS (
            SELECT 1
            FROM tenant_access
            WHERE tenant_access.tenant_id = tenants.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_access_events_actor_user_id", table_name="tenant_access_events")
    op.drop_index("ix_tenant_access_events_tenant_id", table_name="tenant_access_events")
    op.drop_table("tenant_access_events")
    op.drop_index("ix_tenant_access_status_until", table_name="tenant_access")
    op.drop_index("ix_tenant_access_tenant_id", table_name="tenant_access")
    op.drop_table("tenant_access")
