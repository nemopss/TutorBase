"""Add platform broadcast campaigns

Revision ID: 20260419_platform_broadcasts
Revises: 20260419_lesson_package_type
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260419_platform_broadcasts"
down_revision: Union[str, None] = "20260419_lesson_package_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broadcast_campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False, server_default="all_bot_users"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate_limit_per_second", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_task_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcast_campaigns_created_by_user_id", "broadcast_campaigns", ["created_by_user_id"])
    op.create_index(
        "ix_broadcast_campaigns_status_created",
        "broadcast_campaigns",
        ["status", "created_at"],
    )

    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("bot_user_id", sa.Integer(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bot_user_id"], ["bot_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["broadcast_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "chat_id", name="uq_broadcast_recipients_campaign_chat"),
    )
    op.create_index("ix_broadcast_recipients_bot_user_id", "broadcast_recipients", ["bot_user_id"])
    op.create_index("ix_broadcast_recipients_campaign_id", "broadcast_recipients", ["campaign_id"])
    op.create_index(
        "ix_broadcast_recipients_campaign_status",
        "broadcast_recipients",
        ["campaign_id", "status"],
    )

    op.alter_column("broadcast_campaigns", "audience", server_default=None)
    op.alter_column("broadcast_campaigns", "status", server_default=None)
    op.alter_column("broadcast_campaigns", "recipient_count", server_default=None)
    op.alter_column("broadcast_campaigns", "sent_count", server_default=None)
    op.alter_column("broadcast_campaigns", "failed_count", server_default=None)
    op.alter_column("broadcast_campaigns", "skipped_count", server_default=None)
    op.alter_column("broadcast_campaigns", "rate_limit_per_second", server_default=None)
    op.alter_column("broadcast_recipients", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_broadcast_recipients_campaign_status", table_name="broadcast_recipients")
    op.drop_index("ix_broadcast_recipients_campaign_id", table_name="broadcast_recipients")
    op.drop_index("ix_broadcast_recipients_bot_user_id", table_name="broadcast_recipients")
    op.drop_table("broadcast_recipients")
    op.drop_index("ix_broadcast_campaigns_status_created", table_name="broadcast_campaigns")
    op.drop_index("ix_broadcast_campaigns_created_by_user_id", table_name="broadcast_campaigns")
    op.drop_table("broadcast_campaigns")
