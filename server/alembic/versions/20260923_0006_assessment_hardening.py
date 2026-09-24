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

    # 旧代码的 get_or_create_attempt 没有唯一约束也没有行锁，并发下会为同一个
    # (paper_id, student_id) 建出多条 attempt。建约束前必须先收敛历史数据。
    #
    # 保留规则：答案最多的那条优先（前端只会往拿到的那条 attempt 上写答案，
    # 所以有答案的才是学生真正在用的）；活跃行优先于软删行；同样多时留最早的；
    # 再同样时按 id 定序，保证 created_at 完全相同的并列行也能收敛，
    # 否则唯一约束会创建失败。
    #
    # 注意：删除会级联清掉 assessment_answers（ON DELETE CASCADE），
    # behavior_events.attempt_id 则被置 NULL。这些行无法靠 downgrade 恢复，
    # 所以先把要删的 attempt 连同它的答案落一张备份表留痕。
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS assessment_attempts_dedup_backup AS
        SELECT a.*,
               (
                   SELECT jsonb_agg(to_jsonb(x))
                   FROM assessment_answers x
                   WHERE x.attempt_id = a.id
               ) AS archived_answers,
               now() AS archived_at
        FROM assessment_attempts a
        WHERE false
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT a.id,
                   row_number() OVER (
                       PARTITION BY a.paper_id, a.student_id
                       ORDER BY (
                           SELECT count(*) FROM assessment_answers x WHERE x.attempt_id = a.id
                       ) DESC,
                       (a.deleted_at IS NOT NULL) ASC,
                       a.created_at ASC NULLS LAST,
                       a.id ASC
                   ) AS rn
            FROM assessment_attempts a
        )
        INSERT INTO assessment_attempts_dedup_backup
        SELECT a.*,
               (
                   SELECT jsonb_agg(to_jsonb(x))
                   FROM assessment_answers x
                   WHERE x.attempt_id = a.id
               ),
               now()
        FROM assessment_attempts a
        WHERE a.id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT a.id,
                   row_number() OVER (
                       PARTITION BY a.paper_id, a.student_id
                       ORDER BY (
                           SELECT count(*) FROM assessment_answers x WHERE x.attempt_id = a.id
                       ) DESC,
                       (a.deleted_at IS NOT NULL) ASC,
                       a.created_at ASC NULLS LAST,
                       a.id ASC
                   ) AS rn
            FROM assessment_attempts a
        )
        DELETE FROM assessment_attempts
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
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
