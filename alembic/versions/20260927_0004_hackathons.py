"""Hackathons, cases and evaluation criteria."""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0004"
down_revision = "20260927_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hackathons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("deadline_at > starts_at", name="ck_hackathon_dates"),
    )
    op.create_index("ix_hackathons_organizer_id", "hackathons", ["organizer_id"])
    op.create_table("cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hackathon_id", sa.Integer(), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_cases_hackathon_id", "cases", ["hackathon_id"])
    op.create_table("criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Numeric(10, 4), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("min_score >= 0 AND max_score > min_score AND max_score <= 1000", name="ck_criterion_scores"),
        sa.CheckConstraint("weight > 0 AND weight <= 1000", name="ck_criterion_weight"),
        sa.CheckConstraint("position >= 0", name="ck_criterion_position"),
        sa.UniqueConstraint("case_id", "position", name="uq_criterion_position"),
    )
    op.create_index("ix_criteria_case_id", "criteria", ["case_id"])


def downgrade():
    op.drop_table("criteria")
    op.drop_table("cases")
    op.drop_table("hackathons")
