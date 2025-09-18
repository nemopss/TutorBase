"""Add lesson reminders table

Revision ID: 20241005_add_lesson_reminders
Revises: 6890b0706c4c
Create Date: 2024-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20241005_add_lesson_reminders'
down_revision: Union[str, None] = '6890b0706c4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lesson_reminders',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_name', sa.String(), nullable=False),
        sa.Column('chat_identifier', sa.String(), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('days', sa.String(), nullable=True),
        sa.Column('lesson_time', sa.String(), nullable=True),
        sa.Column('lesson_datetime', sa.Text(), nullable=True),
        sa.Column('lead_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('next_run_at', sa.Text(), nullable=True),
        sa.Column('last_notified_at', sa.Text(), nullable=True),
        sa.Column('last_response', sa.String(), nullable=True),
        sa.Column('last_response_at', sa.Text(), nullable=True),
        sa.Column('last_decline_reason', sa.Text(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('lesson_reminders')
