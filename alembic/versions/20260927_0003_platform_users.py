"""Platform profile and roles.

Revision ID: 20260927_0003
Revises: 20260409_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0003"
down_revision = "20260409_0002"
branch_labels = None
depends_on = None

# Migration data is deliberately independent of application constants.
ROLE_PERMISSIONS = {
    "organizer": ("create-hackathon", "manage-hackathon", "assign-expert"),
    "participant": ("create-team", "join-team", "submit-solution"),
    "expert": ("read-assigned-submission", "score-submission"),
}


def upgrade() -> None:
    op.alter_column("users", "birthday", existing_type=sa.Date(), nullable=True)
    op.add_column("users", sa.Column("display_name", sa.String(128), nullable=True))
    connection = op.get_bind()
    actor = connection.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar_one()
    for slug, permissions in ROLE_PERMISSIONS.items():
        role_id = connection.execute(sa.text(
            "INSERT INTO roles (name, slug, created_by) VALUES (:slug, :slug, :actor) RETURNING id"
        ), {"slug": slug, "actor": actor}).scalar_one()
        for permission in permissions:
            permission_id = connection.execute(sa.text(
                "INSERT INTO permissions (name, slug, created_by) "
                "VALUES (:slug, :slug, :actor) RETURNING id"
            ), {"slug": permission, "actor": actor}).scalar_one()
            connection.execute(sa.text(
                "INSERT INTO permission_role (role_id, permission_id, created_by) "
                "SELECT id, :permission, :actor FROM roles WHERE id = :role OR slug = 'admin'"
            ), {"permission": permission_id, "actor": actor, "role": role_id})

    # Existing registered users keep their old assignments and receive the basic role.
    connection.execute(sa.text(
        "INSERT INTO role_user (user_id, role_id, created_by) "
        "SELECT u.id, r.id, :actor FROM users u CROSS JOIN roles r "
        "WHERE r.slug = 'participant' AND u.username != 'Systemrbac'"
    ), {"actor": actor})


def downgrade() -> None:
    connection = op.get_bind()
    # Refuse a lossy downgrade: the old schema requires a birthday for every user.
    if connection.execute(sa.text("SELECT 1 FROM users WHERE birthday IS NULL LIMIT 1")).first():
        raise RuntimeError("Downgrade requires birthdays for all users; no dates are invented.")
    if connection.execute(sa.text("SELECT 1 FROM users WHERE display_name IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Downgrade would lose display names; export/clear them first.")
    for slug, permissions in ROLE_PERMISSIONS.items():
        # FK cascades remove role_user and permission_role assignments.
        connection.execute(sa.text("DELETE FROM roles WHERE slug = :slug"), {"slug": slug})
        for permission in permissions:
            connection.execute(sa.text("DELETE FROM permissions WHERE slug = :slug"), {"slug": permission})
    op.drop_column("users", "display_name")
    op.alter_column("users", "birthday", existing_type=sa.Date(), nullable=False)
