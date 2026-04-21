"""Add learner soft archive

Revision ID: 20260421_add_learner_archive
Revises: 20260420_repair_missing_package_prices
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_add_learner_archive"
down_revision: Union[str, None] = "20260420_repair_missing_package_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learners", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_learners_tenant_archived_display_name",
        "learners",
        ["tenant_id", "archived_at", "display_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_learners_tenant_archived_display_name", table_name="learners")
    op.drop_column("learners", "archived_at")
