"""Add email authentication fields to users

Revision ID: 20260506_email_auth_users
Revises: 20260429_free_start_access
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260506_email_auth_users"
down_revision: Union[str, None] = "20260429_free_start_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("users")}

    with op.batch_alter_table("users") as batch:
        if "email" not in columns:
            batch.add_column(sa.Column("email", sa.String(), nullable=True))
        if "email_normalized" not in columns:
            batch.add_column(sa.Column("email_normalized", sa.String(), nullable=True))
        if "password_hash" not in columns:
            batch.add_column(sa.Column("password_hash", sa.String(), nullable=True))
        if "email_verified_at" not in columns:
            batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "uq_users_email" not in indexes:
        op.create_index("uq_users_email", "users", ["email"], unique=True)
    if "uq_users_email_normalized" not in indexes:
        op.create_index("uq_users_email_normalized", "users", ["email_normalized"], unique=True)


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("users")}
    if "uq_users_email_normalized" in indexes:
        op.drop_index("uq_users_email_normalized", table_name="users")
    if "uq_users_email" in indexes:
        op.drop_index("uq_users_email", table_name="users")

    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    with op.batch_alter_table("users") as batch:
        if "email_verified_at" in columns:
            batch.drop_column("email_verified_at")
        if "password_hash" in columns:
            batch.drop_column("password_hash")
        if "email_normalized" in columns:
            batch.drop_column("email_normalized")
        if "email" in columns:
            batch.drop_column("email")
