"""Create auth tables.

Revision ID: 20260409_0000
Revises:
Create Date: 2026-04-09 20:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создает таблицы и индексы ЛР2: users и auth_sessions."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_users_username_ci", "users", [sa.text("lower(username)")], unique=True)
    op.create_index("uq_users_email_ci", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("access_jti", sa.String(length=64), nullable=False),
        sa.Column("refresh_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])
    op.create_index("ix_auth_sessions_access_jti", "auth_sessions", ["access_jti"], unique=True)
    op.create_index("ix_auth_sessions_refresh_hash", "auth_sessions", ["refresh_hash"])


def downgrade() -> None:
    """Удаляет таблицы и индексы ЛР2: users и auth_sessions."""
    op.drop_index("ix_auth_sessions_refresh_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_access_jti", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("uq_users_email_ci", table_name="users")
    op.drop_index("uq_users_username_ci", table_name="users")
    op.drop_table("users")
