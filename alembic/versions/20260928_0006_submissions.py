"""Submission metadata and S3 object references."""
from alembic import op
import sqlalchemy as sa

revision = "20260928_0006"
down_revision = "20260927_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stored_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_key", sa.String(255), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("size_bytes > 0", name="ck_stored_object_size"),
    )
    op.create_table("submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("stored_object_id", sa.Integer(), sa.ForeignKey("stored_objects.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.CheckConstraint("url IS NOT NULL OR stored_object_id IS NOT NULL", name="ck_submission_content"),
    )
    op.create_index("ix_submissions_team_id", "submissions", ["team_id"])
    op.create_index("ix_submissions_case_id", "submissions", ["case_id"])
    op.create_index("ix_submissions_submitted_by", "submissions", ["submitted_by"])
    op.create_index("ix_submission_team_case_latest", "submissions", ["team_id", "case_id", "submitted_at", "id"])


def downgrade():
    op.drop_table("submissions")
    op.drop_table("stored_objects")
