"""Enforce package type, schedule and renewal invariants.

Revision ID: 20260812_package_invariants
Revises: 20260812_notification_resp_uq
Create Date: 2026-08-12 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260812_package_invariants"
down_revision: Union[str, None] = "20260812_notification_resp_uq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize rows created before package modes were fully enforced.
    op.execute(
        """
        UPDATE lesson_packages
        SET package_type = 'package'
        WHERE package_type NOT IN ('package', 'one_off')
        """
    )
    op.execute(
        """
        UPDATE lesson_packages
        SET schedule_mode = 'flexible'
        WHERE package_type = 'package'
          AND schedule_mode NOT IN ('fixed', 'flexible')
        """
    )
    op.execute(
        """
        UPDATE lesson_packages
        SET schedule_mode = 'one_off', renewal_enabled = false
        WHERE package_type = 'one_off'
        """
    )
    op.execute(
        """
        UPDATE lesson_packages
        SET schedule_mode = 'flexible', renewal_enabled = false
        WHERE package_type = 'package' AND schedule_mode = 'one_off'
        """
    )
    op.execute(
        """
        UPDATE lesson_packages
        SET renewal_enabled = false
        WHERE renewal_enabled = true
          AND (package_type <> 'package' OR schedule_mode <> 'fixed')
        """
    )
    op.create_check_constraint(
        "ck_lesson_packages_type_schedule_mode",
        "lesson_packages",
        "(package_type = 'one_off' AND schedule_mode = 'one_off' AND renewal_enabled = false) "
        "OR (package_type = 'package' AND schedule_mode IN ('fixed', 'flexible'))",
    )
    op.create_check_constraint(
        "ck_lesson_packages_renewal_mode",
        "lesson_packages",
        "renewal_enabled = false OR (package_type = 'package' AND schedule_mode = 'fixed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_lesson_packages_renewal_mode",
        "lesson_packages",
        type_="check",
    )
    op.drop_constraint(
        "ck_lesson_packages_type_schedule_mode",
        "lesson_packages",
        type_="check",
    )
