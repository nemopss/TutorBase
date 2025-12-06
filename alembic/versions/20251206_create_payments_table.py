"""Create payments table

Revision ID: 20251206_payments
Revises: 20251206_lesson_price
Create Date: 2025-12-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251206_payments'
down_revision: Union[str, None] = '20251206_lesson_price'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create payments table with all fields and indexes."""
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('learner_id', sa.Integer(), nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=True),
        sa.Column('lesson_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='RUB'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['learner_id'], ['learners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_id'], ['lesson_packages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payments_tenant_id', 'payments', ['tenant_id'], unique=False)
    op.create_index('ix_payments_tenant_learner', 'payments', ['tenant_id', 'learner_id'], unique=False)
    op.create_index('ix_payments_tenant_paid_at', 'payments', ['tenant_id', 'paid_at'], unique=False)


def downgrade() -> None:
    """Drop payments table and indexes."""
    op.drop_index('ix_payments_tenant_paid_at', table_name='payments')
    op.drop_index('ix_payments_tenant_learner', table_name='payments')
    op.drop_index('ix_payments_tenant_id', table_name='payments')
    op.drop_table('payments')
