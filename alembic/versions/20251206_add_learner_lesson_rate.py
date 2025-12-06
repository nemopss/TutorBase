"""Add lesson_rate field to learners table

Revision ID: 20251206_learner_rate
Revises: ef476b1e75b2
Create Date: 2025-12-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_learner_rate'
down_revision: Union[str, None] = 'ef476b1e75b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lesson_rate column to learners table."""
    op.add_column(
        'learners',
        sa.Column('lesson_rate', sa.Numeric(precision=10, scale=2), nullable=True)
    )


def downgrade() -> None:
    """Remove lesson_rate column from learners table."""
    op.drop_column('learners', 'lesson_rate')
