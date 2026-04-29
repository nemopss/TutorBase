"""Normalize tenant access for the free Start plan

Revision ID: 20260429_free_start_access
Revises: 20260429_legal_acceptances
Create Date: 2026-04-29 00:00:00.000000
"""
from __future__ import annotations

from typing import Union

from alembic import op


revision: str = "20260429_free_start_access"
down_revision: Union[str, None] = "20260429_legal_acceptances"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE tenant_access
        SET
            status = 'lifetime',
            access_until = NULL,
            grace_until = NULL,
            notes = CASE
                WHEN notes IS NULL OR notes = '' THEN 'Normalized for free Start plan'
                ELSE notes
            END,
            updated_at = now()
        WHERE status IN ('trial', 'active', 'grace', 'expired')
        """
    )


def downgrade() -> None:
    # The previous access dates cannot be reconstructed safely.
    pass
