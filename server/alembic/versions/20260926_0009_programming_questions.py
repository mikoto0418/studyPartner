"""programming questions: language, test cases, starter code, judge result

Revision ID: 20260926_0009
Revises: 20260925_0008
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0009"
down_revision = "20260925_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_questions",
        sa.Column("language", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "assessment_questions",
        sa.Column("test_cases", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "assessment_questions",
        sa.Column("starter_code", sa.Text(), nullable=True),
    )
    # 判题产物：{status, passed, total, cases:[{index, passed, status, input, expected, actual, stderr}]}
    op.add_column(
        "assessment_answers",
        sa.Column("judge_result", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessment_answers", "judge_result")
    op.drop_column("assessment_questions", "starter_code")
    op.drop_column("assessment_questions", "test_cases")
    op.drop_column("assessment_questions", "language")
