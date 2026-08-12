"""Make notification responses idempotent per instance.

Revision ID: 20260812_notification_resp_uq
Revises: 20260730_package_modes_outbox
Create Date: 2026-08-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260812_notification_resp_uq"
down_revision: Union[str, None] = "20260730_package_modes_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM notification_responses duplicate
        USING notification_responses original
        WHERE duplicate.notification_instance_id = original.notification_instance_id
          AND duplicate.notification_instance_id IS NOT NULL
          AND duplicate.id > original.id
        """
    )
    op.create_unique_constraint(
        "uq_notification_response_instance",
        "notification_responses",
        ["notification_instance_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_notification_response_instance",
        "notification_responses",
        type_="unique",
    )
