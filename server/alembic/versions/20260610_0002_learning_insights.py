"""add learning insights

Revision ID: 20260610_0002
Revises: 20260609_0001
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260610_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("learning_insights"):
        return

    op.create_table(
        "learning_insights",
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("insight_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("affected_student_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_insights_scope"), "learning_insights", ["scope"], unique=False)
    op.create_index(op.f("ix_learning_insights_class_id"), "learning_insights", ["class_id"], unique=False)
    op.create_index(op.f("ix_learning_insights_student_id"), "learning_insights", ["student_id"], unique=False)
    op.create_index(op.f("ix_learning_insights_teacher_id"), "learning_insights", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_learning_insights_insight_type"), "learning_insights", ["insight_type"], unique=False)
    op.create_index(op.f("ix_learning_insights_severity"), "learning_insights", ["severity"], unique=False)
    op.create_index(op.f("ix_learning_insights_status"), "learning_insights", ["status"], unique=False)
    op.create_index(op.f("ix_learning_insights_source_fingerprint"), "learning_insights", ["source_fingerprint"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("learning_insights"):
        return

    op.drop_index(op.f("ix_learning_insights_source_fingerprint"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_status"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_severity"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_insight_type"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_teacher_id"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_student_id"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_class_id"), table_name="learning_insights")
    op.drop_index(op.f("ix_learning_insights_scope"), table_name="learning_insights")
    op.drop_table("learning_insights")
