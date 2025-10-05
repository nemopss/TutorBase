"""Add users table and audit fields

Revision ID: 20251005_add_users_and_audit
Revises: 20251004_add_lesson_packages_and_rules
Create Date: 2025-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251005_add_users_and_audit'
down_revision: Union[str, None] = '20251004_add_lesson_packages_and_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('telegram_id', sa.BigInteger(), unique=True, nullable=True),
            sa.Column('username', sa.String(), nullable=True),
            sa.Column('display_name', sa.String(), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False, server_default='teacher'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        )

    columns = {col['name'] for col in inspector.get_columns('lesson_packages')}
    if 'updated_by_user_id' not in columns:
        with op.batch_alter_table('lesson_packages') as batch:
            batch.add_column(sa.Column('updated_by_user_id', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                'fk_lesson_packages_updated_by_user_id_users',
                'users',
                ['updated_by_user_id'],
                ['id'],
                ondelete='SET NULL',
            )

    columns = {col['name'] for col in inspector.get_columns('lessons')}
    if 'updated_by_user_id' not in columns:
        with op.batch_alter_table('lessons') as batch:
            batch.add_column(sa.Column('updated_by_user_id', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                'fk_lessons_updated_by_user_id_users',
                'users',
                ['updated_by_user_id'],
                ['id'],
                ondelete='SET NULL',
            )

    indexes = inspector.get_indexes('lesson_packages')
    if not any(idx['name'] == 'ix_lesson_packages_learner_status' for idx in indexes):
        op.create_index('ix_lesson_packages_learner_status', 'lesson_packages', ['learner_id', 'status'])

    indexes = inspector.get_indexes('lessons')
    if not any(idx['name'] == 'ix_lessons_package_scheduled_at' for idx in indexes):
        op.create_index('ix_lessons_package_scheduled_at', 'lessons', ['package_id', 'scheduled_at'])


def downgrade() -> None:
    op.drop_index('ix_lessons_package_scheduled_at', table_name='lessons')
    op.drop_index('ix_lesson_packages_learner_status', table_name='lesson_packages')

    with op.batch_alter_table('lessons') as batch:
        batch.drop_constraint('fk_lessons_updated_by_user_id_users', type_='foreignkey')
        batch.drop_column('updated_by_user_id')

    with op.batch_alter_table('lesson_packages') as batch:
        batch.drop_constraint('fk_lesson_packages_updated_by_user_id_users', type_='foreignkey')
        batch.drop_column('updated_by_user_id')

    op.drop_table('users')
