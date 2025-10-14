"""Add payment reminder kind

Revision ID: 20241011_add_payment_reminder_kind
Revises: 20241006_add_bot_users_learners
Create Date: 2024-10-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20241011_add_payment_reminder_kind'
down_revision: Union[str, None] = '20241006_add_bot_users_learners'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('lesson_reminders')}

    if bind.dialect.name == 'postgresql':
        op.execute(sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))

    if 'kind' not in existing_columns:
        op.add_column(
            'lesson_reminders',
            sa.Column('kind', sa.String(length=32), nullable=False, server_default='lesson')
        )
        op.execute("UPDATE lesson_reminders SET kind = 'lesson' WHERE kind IS NULL")
    else:
        op.execute("UPDATE lesson_reminders SET kind = 'lesson' WHERE kind IS NULL")

    if 'template_key' not in existing_columns:
        op.add_column(
            'lesson_reminders',
            sa.Column('template_key', sa.String(length=64), nullable=True)
        )

    if bind.dialect.name != 'sqlite':
        op.alter_column('lesson_reminders', 'kind', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('lesson_reminders')}

    if 'template_key' in columns:
        op.drop_column('lesson_reminders', 'template_key')
    if 'kind' in columns:
        op.drop_column('lesson_reminders', 'kind')
