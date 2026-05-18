"""Expand free Start plan learner limit

Revision ID: 20260518_start_plan_limit_five
Revises: 20260506_email_verification_tokens
Create Date: 2026-05-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260518_start_plan_limit_five"
down_revision: Union[str, None] = "20260506_email_verification_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE billing_plans
        SET active_learners_limit = 5,
            updated_at = now()
        WHERE code = 'start'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE billing_plans
        SET active_learners_limit = 3,
            updated_at = now()
        WHERE code = 'start'
        """
    )
