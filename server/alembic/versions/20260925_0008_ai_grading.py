"""ai grading: paper grading preference + answer ai suggestion

Revision ID: 20260925_0008
Revises: 20260925_0007
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0008"
down_revision = "20260925_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_papers",
        sa.Column("grading_preference", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "assessment_answers",
        sa.Column("ai_suggested_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "assessment_answers",
        sa.Column("ai_comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "assessment_answers",
        sa.Column("ai_graded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessment_answers", "ai_graded_at")
    op.drop_column("assessment_answers", "ai_comment")
    op.drop_column("assessment_answers", "ai_suggested_score")
    op.drop_column("assessment_papers", "grading_preference")
