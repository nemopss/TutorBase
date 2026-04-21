"""Repair missing package prices from learner rates

Revision ID: 20260420_repair_missing_package_prices
Revises: 20260420_notification_default_statuses
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260420_repair_missing_package_prices"
down_revision: Union[str, None] = "20260420_notification_default_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH repaired AS (
            UPDATE lesson_packages lp
            SET
                price = learners.lesson_rate * lp.total_lessons,
                updated_at = CURRENT_TIMESTAMP
            FROM learners
            WHERE learners.id = lp.learner_id
              AND lp.status IN ('active', 'completed')
              AND lp.package_type = 'package'
              AND (lp.price IS NULL OR lp.price <= 0)
              AND learners.lesson_rate IS NOT NULL
              AND lp.total_lessons IS NOT NULL
              AND lp.total_lessons > 0
            RETURNING lp.id, lp.price
        ),
        paid_by_package AS (
            SELECT
                repaired.id AS package_id,
                COALESCE(SUM(payments.amount), 0) AS paid
            FROM repaired
            LEFT JOIN payments
                ON payments.package_id = repaired.id
               AND payments.voided_at IS NULL
            GROUP BY repaired.id
        )
        UPDATE lesson_packages lp
        SET
            payment_status = CASE
                WHEN paid_by_package.paid <= 0 THEN 'unpaid'
                WHEN paid_by_package.paid < lp.price THEN 'partial'
                ELSE 'paid'
            END,
            updated_at = CURRENT_TIMESTAMP
        FROM paid_by_package
        WHERE paid_by_package.package_id = lp.id
        """
    )


def downgrade() -> None:
    # The repaired prices represent recovered financial facts; do not erase them
    # on downgrade.
    pass
