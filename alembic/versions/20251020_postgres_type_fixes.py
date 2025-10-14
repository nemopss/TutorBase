"""Normalize column types and defaults for PostgreSQL"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20251020_postgres_type_fixes'
down_revision: Union[str, None] = '20251013_perf_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_COLUMNS = [
    ('applications', 'created_at'),
    ('bot_users', 'created_at'),
    ('bot_users', 'updated_at'),
    ('bot_users', 'last_seen_at'),
    ('learners', 'created_at'),
    ('lesson_reminders', 'lesson_datetime'),
    ('lesson_reminders', 'next_run_at'),
    ('lesson_reminders', 'last_notified_at'),
    ('lesson_reminders', 'last_response_at'),
    ('lesson_reminders', 'created_at'),
]


BOOLEAN_DEFAULTS = [
    ('bot_users', 'is_bot', False),
    ('lesson_reminders', 'is_recurring', True),
    ('lesson_reminders', 'active', True),
    ('learners', 'notifications_enabled', True),
    ('reminder_rules', 'active', True),
    ('reminder_instances', 'active', True),
]


JSON_COLUMNS = [
    ('lesson_package_templates', 'default_config'),
    ('reminder_rules', 'config'),
    ('reminder_instances', 'payload'),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            sa.text(
                f'ALTER TABLE {table} '
                f'ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE '
                f'USING NULLIF({column}::text, \'\')::timestamptz'
            )
        )

    for table, column, default in BOOLEAN_DEFAULTS:
        default_literal = 'true' if default else 'false'
        op.execute(
            sa.text(
                f'ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default_literal}'
            )
        )

    for table, column in JSON_COLUMNS:
        op.execute(
            sa.text(
                f'ALTER TABLE {table} '
                f'ALTER COLUMN {column} TYPE JSONB '
                f'USING CASE '
                f'WHEN {column} IS NULL OR {column}::text = \'\' THEN NULL '
                f'ELSE {column}::jsonb '
                f'END'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    for table, column in reversed(JSON_COLUMNS):
        op.execute(
            sa.text(
                f'ALTER TABLE {table} '
                f'ALTER COLUMN {column} TYPE JSON '
                f'USING {column}::json'
            )
        )

    for table, column, _ in BOOLEAN_DEFAULTS:
        op.execute(
            sa.text(
                f'ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT'
            )
        )

    for table, column in reversed(TIMESTAMP_COLUMNS):
        op.execute(
            sa.text(
                f'ALTER TABLE {table} '
                f'ALTER COLUMN {column} TYPE TEXT '
                f'USING {column}::timestamp with time zone::text'
            )
        )
