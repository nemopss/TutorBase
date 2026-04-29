"""Add legal acceptance audit records

Revision ID: 20260429_legal_acceptances
Revises: 20260428_rename_billing_plan_names
Create Date: 2026-04-29 00:00:00.000000
"""
from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260429_legal_acceptances"
down_revision: Union[str, None] = "20260428_rename_billing_plan_names"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("offer_version", sa.String(length=32), nullable=False),
        sa.Column("privacy_version", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_acceptances_tenant_id", "legal_acceptances", ["tenant_id"])
    op.create_index("ix_legal_acceptances_user_id", "legal_acceptances", ["user_id"])
    op.create_index(
        "ix_legal_acceptances_tenant_accepted",
        "legal_acceptances",
        ["tenant_id", "accepted_at"],
    )
    op.create_index(
        "ix_legal_acceptances_user_accepted",
        "legal_acceptances",
        ["user_id", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_user_accepted", table_name="legal_acceptances")
    op.drop_index("ix_legal_acceptances_tenant_accepted", table_name="legal_acceptances")
    op.drop_index("ix_legal_acceptances_user_id", table_name="legal_acceptances")
    op.drop_index("ix_legal_acceptances_tenant_id", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
