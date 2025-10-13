"""add_performance_indexes

Revision ID: 20251013_perf_idx
Revises: 20251009_add_learner_notifications_enabled
Create Date: 2025-10-13

Add indexes for frequently queried fields to improve performance:
- lessons: status, scheduled_at, package_id
- lesson_packages: status, learner_id
- reminder_instances: status, active, scheduled_for
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251013_perf_idx'
down_revision = '20251009_add_learner_notifications_enabled'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lessons table indexes
    op.create_index('ix_lessons_status', 'lessons', ['status'])
    op.create_index('ix_lessons_scheduled_at', 'lessons', ['scheduled_at'])
    op.create_index('ix_lessons_package_id_scheduled_at', 'lessons', ['package_id', 'scheduled_at'])
    
    # Lesson packages indexes
    op.create_index('ix_lesson_packages_status', 'lesson_packages', ['status'])
    op.create_index('ix_lesson_packages_learner_id', 'lesson_packages', ['learner_id'])
    op.create_index('ix_lesson_packages_learner_id_status', 'lesson_packages', ['learner_id', 'status'])
    
    # Reminder instances indexes
    op.create_index('ix_reminder_instances_status', 'reminder_instances', ['status'])
    op.create_index('ix_reminder_instances_active', 'reminder_instances', ['active'])
    op.create_index('ix_reminder_instances_scheduled_for', 'reminder_instances', ['scheduled_for'])
    op.create_index('ix_reminder_instances_active_scheduled', 'reminder_instances', ['active', 'scheduled_for'])


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index('ix_reminder_instances_active_scheduled', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_scheduled_for', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_active', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_status', table_name='reminder_instances')
    
    op.drop_index('ix_lesson_packages_learner_id_status', table_name='lesson_packages')
    op.drop_index('ix_lesson_packages_learner_id', table_name='lesson_packages')
    op.drop_index('ix_lesson_packages_status', table_name='lesson_packages')
    
    op.drop_index('ix_lessons_package_id_scheduled_at', table_name='lessons')
    op.drop_index('ix_lessons_scheduled_at', table_name='lessons')
    op.drop_index('ix_lessons_status', table_name='lessons')
