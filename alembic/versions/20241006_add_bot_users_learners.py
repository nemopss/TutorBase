"""Add bot users and learners tables

Revision ID: 20241006_add_bot_users_learners
Revises: 20241005_add_lesson_reminders
Create Date: 2024-10-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241006_add_bot_users_learners'
down_revision: Union[str, None] = '20241005_add_lesson_reminders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bot_users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('language_code', sa.String(length=10), nullable=True),
        sa.Column('is_bot', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
        sa.Column('last_seen_at', sa.Text(), nullable=False),
        sa.UniqueConstraint('chat_id', name='uq_bot_users_chat_id'),
    )

    op.create_table(
        'learners',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('bot_user_id', sa.Integer(), sa.ForeignKey('bot_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.UniqueConstraint('bot_user_id', name='uq_learners_bot_user_id'),
    )


def downgrade() -> None:
    op.drop_table('learners')
    op.drop_table('bot_users')
