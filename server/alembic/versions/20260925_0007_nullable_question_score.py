"""nullable question score: unset scores stay NULL instead of 0

Revision ID: 20260925_0007
Revises: 20260923_0006
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0007"
down_revision = "20260923_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("assessment_questions"):
        columns = {c["name"]: c for c in inspector.get_columns("assessment_questions")}
        if "score" in columns and not columns["score"]["nullable"]:
            op.alter_column(
                "assessment_questions",
                "score",
                existing_type=sa.Float(),
                nullable=True,
            )
        # 旧代码把「原文没标分值」落成 0.0，与教师真给的 0 分无法区分。
        # 未发布的试卷还没被学生看到，把这些伪造的 0 还原成「未设置」，
        # 让教师在校对页重新填写；已发布试卷保持原样，不动学生已看到的卷面。
        op.execute(
            """
            UPDATE assessment_questions
            SET score = NULL
            WHERE score = 0
              AND paper_id IN (
                  SELECT id FROM assessment_papers WHERE parse_status <> 'published'
              )
            """
        )

    if inspector.has_table("assessment_papers"):
        columns = {c["name"]: c for c in inspector.get_columns("assessment_papers")}
        if "total_score" in columns and not columns["total_score"]["nullable"]:
            op.alter_column(
                "assessment_papers",
                "total_score",
                existing_type=sa.Float(),
                nullable=True,
            )
        # 未发布试卷的满分必须按题目重新算：只要还有一题没设分值，整卷满分就是未知。
        # 只处理 total_score=0 的旧值会漏掉「少数题有分值、多数题没标」的卷子，
        # 留下「56 题里 52 题空着、总分却写着 4.0」这种自相矛盾的数据。
        op.execute(
            """
            UPDATE assessment_papers p
            SET total_score = CASE
                WHEN EXISTS (
                    SELECT 1 FROM assessment_questions q
                    WHERE q.paper_id = p.id AND q.score IS NULL
                ) THEN NULL
                ELSE (
                    SELECT COALESCE(SUM(q.score), 0)
                    FROM assessment_questions q
                    WHERE q.paper_id = p.id
                )
            END
            WHERE p.parse_status <> 'published'
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 回退时 NULL 必须变成 0，否则 NOT NULL 约束加不上去
    if inspector.has_table("assessment_questions"):
        op.execute("UPDATE assessment_questions SET score = 0 WHERE score IS NULL")
        op.alter_column(
            "assessment_questions",
            "score",
            existing_type=sa.Float(),
            nullable=False,
        )

    if inspector.has_table("assessment_papers"):
        op.execute("UPDATE assessment_papers SET total_score = 0 WHERE total_score IS NULL")
        op.alter_column(
            "assessment_papers",
            "total_score",
            existing_type=sa.Float(),
            nullable=False,
        )
