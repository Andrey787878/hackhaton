"""Teams, membership and revocable invitations."""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0005"
down_revision = "20260927_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hackathon_id", sa.Integer(), sa.ForeignKey("hackathons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("captain_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "hackathon_id", name="uq_team_hackathon"),
    )
    op.create_index("ix_teams_hackathon_id", "teams", ["hackathon_id"])
    op.create_index("ix_teams_captain_id", "teams", ["captain_id"])
    op.create_index("uq_team_name_ci", "teams", ["hackathon_id", sa.text("lower(name)")], unique=True)
    op.create_table("team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("hackathon_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["team_id", "hackathon_id"], ["teams.id", "teams.hackathon_id"], ondelete="CASCADE", name="fk_member_team_hackathon"),
        sa.UniqueConstraint("hackathon_id", "user_id", name="uq_member_hackathon_user"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_member_team_user"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_table("invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_invites_team_id", "invites", ["team_id"])
    op.create_index("uq_invite_active_team", "invites", ["team_id"], unique=True, postgresql_where=sa.text("revoked_at IS NULL"))


def downgrade():
    op.drop_table("invites")
    op.drop_table("team_members")
    op.drop_table("teams")
