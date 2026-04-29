"""Rename billing plan display names

Revision ID: 20260428_rename_billing_plan_names
Revises: 20260428_billing_plans_and_subscriptions
Create Date: 2026-04-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260428_rename_billing_plan_names"
down_revision: Union[str, None] = "20260428_billing_plans_and_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE billing_plans SET name = 'Про' WHERE code = 'pro'")
    op.execute("UPDATE billing_plans SET name = 'Бизнес' WHERE code = 'studio'")


def downgrade() -> None:
    op.execute("UPDATE billing_plans SET name = 'Профи' WHERE code = 'pro'")
    op.execute("UPDATE billing_plans SET name = 'Студия' WHERE code = 'studio'")
