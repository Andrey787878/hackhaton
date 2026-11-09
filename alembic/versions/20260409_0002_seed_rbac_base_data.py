"""Seed RBAC base data.

Revision ID: 20260409_0002
Revises: 20260409_0001
Create Date: 2026-04-09 21:20:00
"""

from __future__ import annotations

from typing import Any
import secrets
import bcrypt

from alembic import op
import sqlalchemy as sa


revision = "20260409_0002"
down_revision = "20260409_0001"
branch_labels = None
depends_on = None


ROLE_SLUGS = ("admin", "user", "guest")
ACTION_SLUGS = ("get-list", "read", "create", "update", "delete", "restore")
ENTITY_SLUGS = ("user", "role", "permission")
SEED_USER_USERNAME = "Systemrbac"
SEED_USER_EMAIL = "system.rbac@local.invalid"
SEED_USER_BIRTHDAY = "2000-01-01"
SEED_PERMISSION_SLUGS = tuple(
    f"{action}-{entity}"
    for entity in ENTITY_SLUGS
    for action in ACTION_SLUGS
)


def _resolve_seed_user_id(connection: sa.Connection) -> int:
    """Возвращает id пользователя для заполнения created_by в сидах."""
    existing_user_id = connection.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if existing_user_id is not None:
        return int(existing_user_id)

    inserted_user_id = connection.execute(
        sa.text(
            """
            INSERT INTO users (username, email, password_hash, birthday)
            VALUES (:username, :email, :password_hash, :birthday)
            RETURNING id
            """
        ),
        {
            "username": SEED_USER_USERNAME,
            "email": SEED_USER_EMAIL,
            "password_hash": bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode("ascii"),
            "birthday": SEED_USER_BIRTHDAY,
        },
    ).scalar_one()
    return int(inserted_user_id)


def _build_permission_rows(created_by: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity in ENTITY_SLUGS:
        for action in ACTION_SLUGS:
            slug = f"{action}-{entity}"
            rows.append(
                {
                    "name": slug,
                    "slug": slug,
                    "description": None,
                    "created_by": created_by,
                }
            )
    return rows


def upgrade() -> None:
    """Добавляет базовые роли, разрешения и связи роли-разрешения."""
    connection = op.get_bind()
    seed_user_id = _resolve_seed_user_id(connection)

    role_table = sa.table(
        "roles",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("created_by", sa.Integer()),
    )
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("created_by", sa.Integer()),
    )
    permission_role_table = sa.table(
        "permission_role",
        sa.column("role_id", sa.Integer()),
        sa.column("permission_id", sa.Integer()),
        sa.column("created_by", sa.Integer()),
    )

    connection.execute(
        sa.insert(role_table),
        [
            {"name": "Admin", "slug": "admin", "description": "Администратор", "created_by": seed_user_id},
            {"name": "User", "slug": "user", "description": "Пользователь", "created_by": seed_user_id},
            {"name": "Guest", "slug": "guest", "description": "Гость", "created_by": seed_user_id},
        ],
    )

    connection.execute(sa.insert(permission_table), _build_permission_rows(seed_user_id))

    role_rows = connection.execute(
        sa.text("SELECT id, slug FROM roles WHERE slug = ANY(:slugs)"),
        {"slugs": list(ROLE_SLUGS)},
    ).mappings()
    role_id_by_slug = {row["slug"]: int(row["id"]) for row in role_rows}

    permission_rows = connection.execute(
        sa.text("SELECT id, slug FROM permissions"),
    ).mappings()
    permission_id_by_slug = {row["slug"]: int(row["id"]) for row in permission_rows}

    admin_permission_ids = list(permission_id_by_slug.values())
    user_permission_ids: list[int] = []
    guest_permission_ids: list[int] = []

    permission_role_rows: list[dict[str, int]] = []
    permission_role_rows.extend(
        {
            "role_id": role_id_by_slug["admin"],
            "permission_id": permission_id,
            "created_by": seed_user_id,
        }
        for permission_id in admin_permission_ids
    )
    permission_role_rows.extend(
        {
            "role_id": role_id_by_slug["user"],
            "permission_id": permission_id,
            "created_by": seed_user_id,
        }
        for permission_id in user_permission_ids
    )
    permission_role_rows.extend(
        {
            "role_id": role_id_by_slug["guest"],
            "permission_id": permission_id,
            "created_by": seed_user_id,
        }
        for permission_id in guest_permission_ids
    )

    connection.execute(sa.insert(permission_role_table), permission_role_rows)


def downgrade() -> None:
    """Удаляет сиды ролей, разрешений и их связей."""
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DELETE FROM permission_role
            WHERE role_id IN (SELECT id FROM roles WHERE slug = ANY(:role_slugs))
            """
        ),
        {"role_slugs": list(ROLE_SLUGS)},
    )

    connection.execute(
        sa.text("DELETE FROM permissions WHERE slug = ANY(:permission_slugs)"),
        {
            "permission_slugs": list(SEED_PERMISSION_SLUGS),
        },
    )
    connection.execute(
        sa.text("DELETE FROM roles WHERE slug = ANY(:role_slugs)"),
        {"role_slugs": list(ROLE_SLUGS)},
    )

    # Удаляем fallback-пользователя только если он точно совпадает с seed-профилем
    # и не используется другими сущностями.
    connection.execute(
        sa.text(
            """
            DELETE FROM users
            WHERE username = :username
              AND email = :email
              AND birthday = :birthday
              AND NOT EXISTS (
                    SELECT 1 FROM auth_sessions s
                    WHERE s.user_id = users.id
              )
              AND NOT EXISTS (
                    SELECT 1 FROM role_user ru
                    WHERE ru.user_id = users.id
                       OR ru.created_by = users.id
                       OR ru.deleted_by = users.id
              )
              AND NOT EXISTS (
                    SELECT 1 FROM permission_role pr
                    WHERE pr.created_by = users.id
                       OR pr.deleted_by = users.id
              )
              AND NOT EXISTS (
                    SELECT 1 FROM roles r
                    WHERE r.created_by = users.id
                       OR r.deleted_by = users.id
              )
              AND NOT EXISTS (
                    SELECT 1 FROM permissions p
                    WHERE p.created_by = users.id
                       OR p.deleted_by = users.id
              )
            """
        ),
        {
            "username": SEED_USER_USERNAME,
            "email": SEED_USER_EMAIL,
            "birthday": SEED_USER_BIRTHDAY,
        },
    )
