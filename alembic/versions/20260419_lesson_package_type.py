"""Add lesson package type for one-off lessons

Revision ID: 20260419_lesson_package_type
Revises: 20260419_payment_audit_and_void
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260419_lesson_package_type"
down_revision: Union[str, None] = "20260419_payment_audit_and_void"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lesson_packages",
        sa.Column("package_type", sa.String(length=32), nullable=False, server_default="package"),
    )
    op.create_index(
        "ix_lesson_packages_tenant_type_status",
        "lesson_packages",
        ["tenant_id", "package_type", "status"],
    )
    op.alter_column("lesson_packages", "package_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_lesson_packages_tenant_type_status", table_name="lesson_packages")
    op.drop_column("lesson_packages", "package_type")
