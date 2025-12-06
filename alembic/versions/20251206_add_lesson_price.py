"""Add price field to lessons table

Revision ID: 20251206_lesson_price
Revises: 20251206_pkg_finance
Create Date: 2025-12-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_lesson_price'
down_revision: Union[str, None] = '20251206_pkg_finance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add price column to lessons table for standalone lessons."""
    op.add_column(
        'lessons',
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True)
    )


def downgrade() -> None:
    """Remove price column from lessons table."""
    op.drop_column('lessons', 'price')
