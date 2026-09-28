"""Expert assignments and criterion scores."""
from alembic import op
import sqlalchemy as sa

revision = "20260928_0007"
down_revision = "20260928_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("expert_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expert_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("submission_id", "expert_id", name="uq_expert_assignment"),
    )
    op.create_index("ix_expert_assignments_submission_id", "expert_assignments", ["submission_id"])
    op.create_index("ix_expert_assignments_expert_id", "expert_assignments", ["expert_id"])
    op.create_table("scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("expert_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_id", sa.Integer(), sa.ForeignKey("criteria.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.UniqueConstraint("assignment_id", "criterion_id", name="uq_score_assignment_criterion"),
        sa.CheckConstraint("value >= 0 AND value <= 1000", name="ck_score_value"),
    )
    op.create_index("ix_scores_assignment_id", "scores", ["assignment_id"])
    op.create_index("ix_scores_criterion_id", "scores", ["criterion_id"])


def downgrade():
    op.drop_table("scores")
    op.drop_table("expert_assignments")
