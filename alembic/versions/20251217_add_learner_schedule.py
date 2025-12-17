"""Add learner_id to lesson_package_templates for learner schedules.

Revision ID: 20251217_learner_schedule
Revises: ef476b1e75b2
Create Date: 2025-12-17

This migration repurposes the lesson_package_templates table to store
learner schedules. Each learner can have a personal weekly schedule
stored as JSON in the default_config column.

Changes:
- Add learner_id column with foreign key to learners.id
- Add index for quick lookup by learner_id
- Remove unique constraint on name column (schedules don't need unique names)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251217_learner_schedule'
down_revision = '20251206_payments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add learner_id column (nullable for existing templates)
    op.add_column(
        'lesson_package_templates',
        sa.Column('learner_id', sa.Integer(), nullable=True)
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_lesson_package_templates_learner_id',
        'lesson_package_templates',
        'learners',
        ['learner_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Add index for quick lookup by learner_id
    op.create_index(
        'ix_lesson_package_templates_learner',
        'lesson_package_templates',
        ['learner_id']
    )
    
    # Remove unique constraint on name column
    # Note: The constraint name may vary, trying common patterns
    try:
        op.drop_constraint('lesson_package_templates_name_key', 'lesson_package_templates', type_='unique')
    except Exception:
        try:
            op.drop_constraint('uq_lesson_package_templates_name', 'lesson_package_templates', type_='unique')
        except Exception:
            # Constraint might not exist or have different name
            pass


def downgrade() -> None:
    # Re-add unique constraint on name
    op.create_unique_constraint(
        'lesson_package_templates_name_key',
        'lesson_package_templates',
        ['name']
    )
    
    # Drop index
    op.drop_index('ix_lesson_package_templates_learner', 'lesson_package_templates')
    
    # Drop foreign key
    op.drop_constraint(
        'fk_lesson_package_templates_learner_id',
        'lesson_package_templates',
        type_='foreignkey'
    )
    
    # Drop column
    op.drop_column('lesson_package_templates', 'learner_id')
