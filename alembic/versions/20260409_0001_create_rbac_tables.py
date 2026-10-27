"""Create RBAC tables.

Revision ID: 20260409_0001
Revises: 20260409_0000
Create Date: 2026-04-09 21:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0001"
down_revision = "20260409_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создает таблицы и индексы для RBAC."""
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
        sa.UniqueConstraint("slug", name="uq_roles_slug"),
    )
    op.create_index("ix_roles_created_by", "roles", ["created_by"])
    op.create_index("ix_roles_deleted_by", "roles", ["deleted_by"])
    op.create_index("ix_roles_deleted_at", "roles", ["deleted_at"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
        sa.UniqueConstraint("slug", name="uq_permissions_slug"),
    )
    op.create_index("ix_permissions_created_by", "permissions", ["created_by"])
    op.create_index("ix_permissions_deleted_by", "permissions", ["deleted_by"])
    op.create_index("ix_permissions_deleted_at", "permissions", ["deleted_at"])

    op.create_table(
        "role_user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_role_user_user_id_role_id"),
    )
    op.create_index("ix_role_user_user_id", "role_user", ["user_id"])
    op.create_index("ix_role_user_role_id", "role_user", ["role_id"])
    op.create_index("ix_role_user_created_by", "role_user", ["created_by"])
    op.create_index("ix_role_user_deleted_by", "role_user", ["deleted_by"])
    op.create_index("ix_role_user_deleted_at", "role_user", ["deleted_at"])

    op.create_table(
        "permission_role",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_permission_role_role_id_permission_id"),
    )
    op.create_index("ix_permission_role_role_id", "permission_role", ["role_id"])
    op.create_index("ix_permission_role_permission_id", "permission_role", ["permission_id"])
    op.create_index("ix_permission_role_created_by", "permission_role", ["created_by"])
    op.create_index("ix_permission_role_deleted_by", "permission_role", ["deleted_by"])
    op.create_index("ix_permission_role_deleted_at", "permission_role", ["deleted_at"])


def downgrade() -> None:
    """Удаляет таблицы и индексы RBAC."""
    op.drop_index("ix_permission_role_deleted_at", table_name="permission_role")
    op.drop_index("ix_permission_role_deleted_by", table_name="permission_role")
    op.drop_index("ix_permission_role_created_by", table_name="permission_role")
    op.drop_index("ix_permission_role_permission_id", table_name="permission_role")
    op.drop_index("ix_permission_role_role_id", table_name="permission_role")
    op.drop_table("permission_role")

    op.drop_index("ix_role_user_deleted_at", table_name="role_user")
    op.drop_index("ix_role_user_deleted_by", table_name="role_user")
    op.drop_index("ix_role_user_created_by", table_name="role_user")
    op.drop_index("ix_role_user_role_id", table_name="role_user")
    op.drop_index("ix_role_user_user_id", table_name="role_user")
    op.drop_table("role_user")

    op.drop_index("ix_permissions_deleted_at", table_name="permissions")
    op.drop_index("ix_permissions_deleted_by", table_name="permissions")
    op.drop_index("ix_permissions_created_by", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_deleted_at", table_name="roles")
    op.drop_index("ix_roles_deleted_by", table_name="roles")
    op.drop_index("ix_roles_created_by", table_name="roles")
    op.drop_table("roles")
