"""assessment hardening: unique attempt per (paper, student)

Revision ID: 20260923_0006
Revises: 20260921_0005
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260923_0006"
down_revision = "20260921_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("assessment_attempts"):
        return

    existing = {c["name"] for c in inspector.get_unique_constraints("assessment_attempts")}
    if "uq_assessment_attempts_paper_student" in existing:
        return

    # 清理历史重复：同一 (paper_id, student_id) 只保留最早一条，
    # 其后的作答记录连带答案一并删除，避免约束创建失败。
    op.execute(
        """
        DELETE FROM assessment_attempts a
        USING assessment_attempts b
        WHERE a.paper_id = b.paper_id
          AND a.student_id = b.student_id
          AND a.created_at > b.created_at
        """
    )
    op.create_unique_constraint(
        "uq_assessment_attempts_paper_student",
        "assessment_attempts",
        ["paper_id", "student_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("assessment_attempts"):
        return
    existing = {c["name"] for c in inspector.get_unique_constraints("assessment_attempts")}
    if "uq_assessment_attempts_paper_student" in existing:
        op.drop_constraint(
            "uq_assessment_attempts_paper_student",
            "assessment_attempts",
            type_="unique",
        )
