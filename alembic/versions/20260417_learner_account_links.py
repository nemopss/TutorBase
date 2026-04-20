"""Add learner account link history

Revision ID: 20260417_learner_account_links
Revises: 20260414_notification_parity
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_learner_account_links"
down_revision: Union[str, None] = "20260414_notification_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learner_account_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_user_id", sa.Integer(), sa.ForeignKey("bot_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("unlink_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learner_account_links_tenant_id", "learner_account_links", ["tenant_id"])
    op.create_index("ix_learner_account_links_learner_id", "learner_account_links", ["learner_id"])
    op.create_index("ix_learner_account_links_bot_user_id", "learner_account_links", ["bot_user_id"])
    op.create_index("ix_learner_account_links_user_id", "learner_account_links", ["user_id"])
    op.create_index("ix_learner_account_links_telegram_id", "learner_account_links", ["telegram_id"])
    op.create_index(
        "ix_learner_account_links_active",
        "learner_account_links",
        ["tenant_id", "learner_id", "unlinked_at"],
    )
    op.create_index(
        "ix_learner_account_links_tenant_telegram",
        "learner_account_links",
        ["tenant_id", "telegram_id"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO learner_account_links (
                tenant_id,
                learner_id,
                bot_user_id,
                user_id,
                telegram_id,
                linked_at,
                created_at
            )
            SELECT
                learners.tenant_id,
                learners.id,
                learners.bot_user_id,
                users.id,
                bot_users.chat_id,
                learners.created_at,
                NOW()
            FROM learners
            JOIN bot_users ON bot_users.id = learners.bot_user_id
            LEFT JOIN users ON users.telegram_id = bot_users.chat_id
            WHERE learners.bot_user_id IS NOT NULL
            """
        )
    )

    op.drop_constraint("learners_bot_user_id_fkey", "learners", type_="foreignkey")
    op.alter_column("learners", "bot_user_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "learners_bot_user_id_fkey",
        "learners",
        "bot_users",
        ["bot_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("learners_bot_user_id_fkey", "learners", type_="foreignkey")
    op.alter_column("learners", "bot_user_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "learners_bot_user_id_fkey",
        "learners",
        "bot_users",
        ["bot_user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index("ix_learner_account_links_tenant_telegram", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_active", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_telegram_id", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_user_id", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_bot_user_id", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_learner_id", table_name="learner_account_links")
    op.drop_index("ix_learner_account_links_tenant_id", table_name="learner_account_links")
    op.drop_table("learner_account_links")
