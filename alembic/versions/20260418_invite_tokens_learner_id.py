"""Add learner-scoped invite tokens

Revision ID: 20260418_invite_tokens_learner_id
Revises: 20260417_learner_account_links
Create Date: 2026-04-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260418_invite_tokens_learner_id"
down_revision: Union[str, None] = "20260417_learner_account_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invite_tokens", sa.Column("learner_id", sa.Integer(), nullable=True))
    op.create_index("ix_invite_tokens_learner_id", "invite_tokens", ["learner_id"])
    op.create_foreign_key(
        "invite_tokens_learner_id_fkey",
        "invite_tokens",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("invite_tokens_learner_id_fkey", "invite_tokens", type_="foreignkey")
    op.drop_index("ix_invite_tokens_learner_id", table_name="invite_tokens")
    op.drop_column("invite_tokens", "learner_id")
