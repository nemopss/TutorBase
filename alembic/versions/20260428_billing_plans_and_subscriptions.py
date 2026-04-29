"""Add billing plans and tenant subscriptions

Revision ID: 20260428_billing_plans_and_subscriptions
Revises: 20260423_add_notification_activity_acknowledgements
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260428_billing_plans_and_subscriptions"
down_revision: Union[str, None] = "20260423_add_notification_activity_acknowledgements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("active_learners_limit", sa.Integer(), nullable=False),
        sa.Column("monthly_price_rub", sa.Integer(), nullable=False),
        sa.Column("yearly_price_rub", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("provider_customer_id", sa.String(), nullable=True),
        sa.Column("provider_payment_id", sa.String(), nullable=True),
        sa.Column("provider_subscription_id", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_code"], ["billing_plans.code"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])
    op.create_index("ix_tenant_subscriptions_plan_code", "tenant_subscriptions", ["plan_code"])
    op.create_index("ix_tenant_subscriptions_status", "tenant_subscriptions", ["status"])
    op.create_index(
        "ix_tenant_subscriptions_status_period",
        "tenant_subscriptions",
        ["status", "current_period_end"],
    )
    op.create_index(
        "ix_tenant_subscriptions_provider_subscription",
        "tenant_subscriptions",
        ["provider", "provider_subscription_id"],
    )

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["tenant_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_events_tenant_id", "billing_events", ["tenant_id"])
    op.create_index("ix_billing_events_subscription_id", "billing_events", ["subscription_id"])
    op.create_index("ix_billing_events_actor_user_id", "billing_events", ["actor_user_id"])

    op.execute(
        """
        INSERT INTO billing_plans (
            code,
            name,
            active_learners_limit,
            monthly_price_rub,
            yearly_price_rub,
            is_public,
            display_order,
            created_at,
            updated_at
        )
        VALUES
            ('start', 'Старт', 3, 0, NULL, true, 10, now(), now()),
            ('basic', 'Базовый', 10, 349, 3490, true, 20, now(), now()),
            ('pro', 'Профи', 20, 649, 6490, true, 30, now(), now()),
            ('studio', 'Студия', 50, 1190, 11900, true, 40, now(), now())
        """
    )

    op.execute(
        """
        INSERT INTO tenant_subscriptions (
            tenant_id,
            plan_code,
            status,
            provider,
            cancel_at_period_end,
            notes,
            created_at,
            updated_at
        )
        SELECT
            tenants.id,
            'start',
            'active',
            'manual',
            false,
            'Backfilled during billing migration',
            now(),
            now()
        FROM tenants
        WHERE NOT EXISTS (
            SELECT 1
            FROM tenant_subscriptions
            WHERE tenant_subscriptions.tenant_id = tenants.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_billing_events_actor_user_id", table_name="billing_events")
    op.drop_index("ix_billing_events_subscription_id", table_name="billing_events")
    op.drop_index("ix_billing_events_tenant_id", table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index("ix_tenant_subscriptions_provider_subscription", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_status_period", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_status", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_plan_code", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_id", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")
    op.drop_table("billing_plans")
