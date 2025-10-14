"""Add notifications_enabled to learners

Revision ID: 20251009_add_learner_notifications_enabled
Revises: 20251005_add_users_and_audit
Create Date: 2025-10-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251009_add_learner_notifications_enabled'
down_revision: Union[str, None] = '20251005_add_users_and_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('learners')}

    if 'notifications_enabled' not in existing_columns:
        op.add_column(
            'learners',
            sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true())
        )
        # Remove server_default after setting initial values
        if bind.dialect.name != 'sqlite':
            op.alter_column('learners', 'notifications_enabled', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('learners')}

    if 'notifications_enabled' in columns:
        op.drop_column('learners', 'notifications_enabled')
