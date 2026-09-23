"""add assessment

Revision ID: 20260921_0004
Revises: 20260910_0003
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0004"
down_revision = "20260910_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not sa.inspect(bind).has_table("assessment_papers"):
        op.create_table(
            "assessment_papers",
            sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("parse_status", sa.String(length=30), nullable=False),
            sa.Column("parse_progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("parse_error", sa.Text(), nullable=True),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column("total_score", sa.Float(), nullable=False),
            sa.Column("publish_target", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_file_id"], ["files.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_assessment_papers_creator_id"), "assessment_papers", ["creator_id"], unique=False)
        op.create_index(op.f("ix_assessment_papers_source_file_id"), "assessment_papers", ["source_file_id"], unique=False)

    if not sa.inspect(bind).has_table("assessment_questions"):
        op.create_table(
            "assessment_questions",
            sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("question_type", sa.String(length=30), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("stem_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("analysis", sa.Text(), nullable=True),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("difficulty", sa.Float(), nullable=True),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("source_chunk", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_assessment_questions_paper_id"), "assessment_questions", ["paper_id"], unique=False)

    if not sa.inspect(bind).has_table("assessment_assignments"):
        op.create_table(
            "assessment_assignments",
            sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_type", sa.String(length=30), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("paper_id", "user_id", name="uq_assessment_assignments_paper_user"),
        )
        op.create_index(op.f("ix_assessment_assignments_paper_id"), "assessment_assignments", ["paper_id"], unique=False)
        op.create_index(op.f("ix_assessment_assignments_user_id"), "assessment_assignments", ["user_id"], unique=False)
        op.create_index(op.f("ix_assessment_assignments_class_id"), "assessment_assignments", ["class_id"], unique=False)

    if not sa.inspect(bind).has_table("assessment_attempts"):
        op.create_table(
            "assessment_attempts",
            sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("suspicious", sa.Boolean(), nullable=False),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["assignment_id"], ["assessment_assignments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_assessment_attempts_paper_id"), "assessment_attempts", ["paper_id"], unique=False)
        op.create_index(op.f("ix_assessment_attempts_student_id"), "assessment_attempts", ["student_id"], unique=False)

    if not sa.inspect(bind).has_table("assessment_answers"):
        op.create_table(
            "assessment_answers",
            sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_correct", sa.Boolean(), nullable=True),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("graded", sa.Boolean(), nullable=False),
            sa.Column("time_spent_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["assessment_questions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("attempt_id", "question_id", name="uq_assessment_answers_attempt_question"),
        )
        op.create_index(op.f("ix_assessment_answers_attempt_id"), "assessment_answers", ["attempt_id"], unique=False)
        op.create_index(op.f("ix_assessment_answers_question_id"), "assessment_answers", ["question_id"], unique=False)

    if not sa.inspect(bind).has_table("behavior_events"):
        op.create_table(
            "behavior_events",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_behavior_events_user_id"), "behavior_events", ["user_id"], unique=False)
        op.create_index(op.f("ix_behavior_events_session_id"), "behavior_events", ["session_id"], unique=False)
        op.create_index(op.f("ix_behavior_events_attempt_id"), "behavior_events", ["attempt_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    if sa.inspect(bind).has_table("behavior_events"):
        op.drop_index(op.f("ix_behavior_events_attempt_id"), table_name="behavior_events")
        op.drop_index(op.f("ix_behavior_events_session_id"), table_name="behavior_events")
        op.drop_index(op.f("ix_behavior_events_user_id"), table_name="behavior_events")
        op.drop_table("behavior_events")

    if sa.inspect(bind).has_table("assessment_answers"):
        op.drop_index(op.f("ix_assessment_answers_question_id"), table_name="assessment_answers")
        op.drop_index(op.f("ix_assessment_answers_attempt_id"), table_name="assessment_answers")
        op.drop_table("assessment_answers")

    if sa.inspect(bind).has_table("assessment_attempts"):
        op.drop_index(op.f("ix_assessment_attempts_student_id"), table_name="assessment_attempts")
        op.drop_index(op.f("ix_assessment_attempts_paper_id"), table_name="assessment_attempts")
        op.drop_table("assessment_attempts")

    if sa.inspect(bind).has_table("assessment_assignments"):
        op.drop_index(op.f("ix_assessment_assignments_class_id"), table_name="assessment_assignments")
        op.drop_index(op.f("ix_assessment_assignments_user_id"), table_name="assessment_assignments")
        op.drop_index(op.f("ix_assessment_assignments_paper_id"), table_name="assessment_assignments")
        op.drop_table("assessment_assignments")

    if sa.inspect(bind).has_table("assessment_questions"):
        op.drop_index(op.f("ix_assessment_questions_paper_id"), table_name="assessment_questions")
        op.drop_table("assessment_questions")

    if sa.inspect(bind).has_table("assessment_papers"):
        op.drop_index(op.f("ix_assessment_papers_source_file_id"), table_name="assessment_papers")
        op.drop_index(op.f("ix_assessment_papers_creator_id"), table_name="assessment_papers")
        op.drop_table("assessment_papers")