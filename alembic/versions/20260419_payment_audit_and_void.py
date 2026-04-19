"""Add payment audit and soft void support

Revision ID: 20260419_payment_audit_and_void
Revises: 20260418_tenant_access
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260419_payment_audit_and_void"
down_revision: Union[str, None] = "20260418_tenant_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("voided_by_user_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "payments_updated_by_user_id_fkey",
        "payments",
        "users",
        ["updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "payments_voided_by_user_id_fkey",
        "payments",
        "users",
        ["voided_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_payments_tenant_voided", "payments", ["tenant_id", "voided_at"])

    op.create_table(
        "payment_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_audit_events_payment_id", "payment_audit_events", ["payment_id"])
    op.create_index("ix_payment_audit_events_tenant_id", "payment_audit_events", ["tenant_id"])
    op.create_index("ix_payment_audit_events_actor_user_id", "payment_audit_events", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_audit_events_actor_user_id", table_name="payment_audit_events")
    op.drop_index("ix_payment_audit_events_tenant_id", table_name="payment_audit_events")
    op.drop_index("ix_payment_audit_events_payment_id", table_name="payment_audit_events")
    op.drop_table("payment_audit_events")

    op.drop_index("ix_payments_tenant_voided", table_name="payments")
    op.drop_constraint("payments_voided_by_user_id_fkey", "payments", type_="foreignkey")
    op.drop_constraint("payments_updated_by_user_id_fkey", "payments", type_="foreignkey")
    op.drop_column("payments", "void_reason")
    op.drop_column("payments", "voided_by_user_id")
    op.drop_column("payments", "voided_at")
    op.drop_column("payments", "updated_by_user_id")
