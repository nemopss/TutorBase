"""Add lesson packages, lessons, and reminder rules

Revision ID: 20251004_add_lesson_packages_and_rules
Revises: 20241011_add_payment_reminder_kind
Create Date: 2025-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251004_add_lesson_packages_and_rules'
down_revision: Union[str, None] = '20241011_add_payment_reminder_kind'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lesson_package_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('lesson_count', sa.Integer(), nullable=True),
        sa.Column('duration_days', sa.Integer(), nullable=True),
        sa.Column('default_timezone', sa.String(length=64), nullable=False, server_default='Europe/Moscow'),
        sa.Column('default_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'lesson_packages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('learner_id', sa.Integer(), sa.ForeignKey('learners.id', ondelete='CASCADE'), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('lesson_package_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Europe/Moscow'),
        sa.Column('total_lessons', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'lessons',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('package_id', sa.Integer(), sa.ForeignKey('lesson_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='scheduled'),
        sa.Column('sequence_index', sa.Integer(), nullable=True),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.Column('homework_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'reminder_rules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('package_id', sa.Integer(), sa.ForeignKey('lesson_packages.id', ondelete='CASCADE'), nullable=True),
        sa.Column('lesson_id', sa.Integer(), sa.ForeignKey('lessons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('reminder_type', sa.String(length=32), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('channel', sa.String(length=32), nullable=False, server_default='telegram'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("NOT (package_id IS NULL AND lesson_id IS NULL)", name='ck_reminder_scope'),
    )

    op.create_table(
        'reminder_instances',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('reminder_rules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('package_id', sa.Integer(), sa.ForeignKey('lesson_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lesson_id', sa.Integer(), sa.ForeignKey('lessons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('learner_id', sa.Integer(), sa.ForeignKey('learners.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='scheduled'),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('chat_identifier', sa.String(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('last_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_response', sa.String(), nullable=True),
        sa.Column('last_response_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_decline_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_lesson_packages_learner_id', 'lesson_packages', ['learner_id'])
    op.create_index('ix_lesson_packages_status', 'lesson_packages', ['status'])
    op.create_index('ix_lessons_package_id', 'lessons', ['package_id'])
    op.create_index('ix_lessons_scheduled_at', 'lessons', ['scheduled_at'])
    op.create_index('ix_reminder_rules_package_id', 'reminder_rules', ['package_id'])
    op.create_index('ix_reminder_rules_lesson_id', 'reminder_rules', ['lesson_id'])
    op.create_index('ix_reminder_instances_rule_id', 'reminder_instances', ['rule_id'])
    op.create_index('ix_reminder_instances_scheduled_for', 'reminder_instances', ['scheduled_for'])
    op.create_index('ix_reminder_instances_status', 'reminder_instances', ['status'])


def downgrade() -> None:
    op.drop_index('ix_reminder_instances_status', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_scheduled_for', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_rule_id', table_name='reminder_instances')
    op.drop_index('ix_reminder_rules_lesson_id', table_name='reminder_rules')
    op.drop_index('ix_reminder_rules_package_id', table_name='reminder_rules')
    op.drop_index('ix_lessons_scheduled_at', table_name='lessons')
    op.drop_index('ix_lessons_package_id', table_name='lessons')
    op.drop_index('ix_lesson_packages_status', table_name='lesson_packages')
    op.drop_index('ix_lesson_packages_learner_id', table_name='lesson_packages')
    op.drop_table('reminder_instances')
    op.drop_table('reminder_rules')
    op.drop_table('lessons')
    op.drop_table('lesson_packages')
    op.drop_table('lesson_package_templates')
