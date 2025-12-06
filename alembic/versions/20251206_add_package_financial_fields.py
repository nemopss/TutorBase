"""Add price and payment_status fields to lesson_packages table

Revision ID: 20251206_pkg_finance
Revises: 20251206_learner_rate
Create Date: 2025-12-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_pkg_finance'
down_revision: Union[str, None] = '20251206_learner_rate'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add price and payment_status columns to lesson_packages table."""
    op.add_column(
        'lesson_packages',
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    op.add_column(
        'lesson_packages',
        sa.Column('payment_status', sa.String(16), nullable=False, server_default='unpaid')
    )


def downgrade() -> None:
    """Remove price and payment_status columns from lesson_packages table."""
    op.drop_column('lesson_packages', 'payment_status')
    op.drop_column('lesson_packages', 'price')
