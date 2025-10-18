"""Add tenant performance indexes

Revision ID: 20251018_120000_add_tenant_performance_indexes
Revises: 4cd0823487b7
Create Date: 2025-01-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251018_120000_add_tenant_performance_indexes'
down_revision: Union[str, None] = '4cd0823487b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add performance indexes for tenant-based queries
    
    # Learners indexes
    op.create_index('ix_learners_tenant_display_name', 'learners', ['tenant_id', 'display_name'])
    op.create_index('ix_learners_tenant_created', 'learners', ['tenant_id', 'created_at'])
    
    # Lessons indexes
    op.create_index('ix_lessons_tenant_scheduled', 'lessons', ['tenant_id', 'scheduled_at'])
    op.create_index('ix_lessons_tenant_status', 'lessons', ['tenant_id', 'status'])
    
    # Reminder instances indexes
    op.create_index('ix_reminder_instances_tenant_scheduled', 'reminder_instances', ['tenant_id', 'scheduled_for'])
    op.create_index('ix_reminder_instances_tenant_status_active', 'reminder_instances', ['tenant_id', 'status', 'active'])
    op.create_index('ix_reminder_instances_active_scheduled', 'reminder_instances', ['active', 'scheduled_for'])


def downgrade() -> None:
    # Remove performance indexes
    op.drop_index('ix_reminder_instances_active_scheduled', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_tenant_status_active', table_name='reminder_instances')
    op.drop_index('ix_reminder_instances_tenant_scheduled', table_name='reminder_instances')
    op.drop_index('ix_lessons_tenant_status', table_name='lessons')
    op.drop_index('ix_lessons_tenant_scheduled', table_name='lessons')
    op.drop_index('ix_learners_tenant_created', table_name='learners')
    op.drop_index('ix_learners_tenant_display_name', table_name='learners')