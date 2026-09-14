"""add memory wiki

Revision ID: 20260910_0003
Revises: 20260610_0002
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260910_0003"
down_revision = "20260610_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not sa.inspect(bind).has_table("memory_pages"):
        op.create_table(
            "memory_pages",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slug", sa.String(length=160), nullable=False),
            sa.Column("page_type", sa.String(length=30), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("source_review_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["source_review_id"], ["daily_reviews.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "slug", name="uq_memory_pages_user_slug"),
        )
        op.create_index(op.f("ix_memory_pages_user_id"), "memory_pages", ["user_id"], unique=False)
        op.create_index(op.f("ix_memory_pages_status"), "memory_pages", ["status"], unique=False)
        op.create_index(op.f("ix_memory_pages_page_type"), "memory_pages", ["page_type"], unique=False)

    if not sa.inspect(bind).has_table("memory_sources"):
        op.create_table(
            "memory_sources",
            sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("source_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("snippet", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["page_id"], ["memory_pages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_memory_sources_page_id"), "memory_sources", ["page_id"], unique=False)
        op.create_index(op.f("ix_memory_sources_user_id"), "memory_sources", ["user_id"], unique=False)

    if not sa.inspect(bind).has_table("memory_links"):
        op.create_table(
            "memory_links",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("from_page_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("to_page_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("relation", sa.String(length=40), nullable=False),
            sa.Column("strength", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["from_page_id"], ["memory_pages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_page_id"], ["memory_pages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "from_page_id", "to_page_id", "relation", name="uq_memory_links_user_from_to_relation"),
        )
        op.create_index(op.f("ix_memory_links_user_id"), "memory_links", ["user_id"], unique=False)
        op.create_index(op.f("ix_memory_links_from_page_id"), "memory_links", ["from_page_id"], unique=False)
        op.create_index(op.f("ix_memory_links_to_page_id"), "memory_links", ["to_page_id"], unique=False)

    if not sa.inspect(bind).has_table("memory_events"):
        op.create_table(
            "memory_events",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("operator", sa.String(length=30), nullable=False),
            sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["page_id"], ["memory_pages.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["review_id"], ["daily_reviews.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_memory_events_user_id"), "memory_events", ["user_id"], unique=False)
        op.create_index(op.f("ix_memory_events_page_id"), "memory_events", ["page_id"], unique=False)

    if not sa.inspect(bind).has_table("memory_review_tasks"):
        op.create_table(
            "memory_review_tasks",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("task_type", sa.String(length=40), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_by", sa.String(length=30), nullable=False),
            sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("handled_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("handled_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.ForeignKeyConstraint(["handled_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["page_id"], ["memory_pages.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_memory_review_tasks_user_id"), "memory_review_tasks", ["user_id"], unique=False)
        op.create_index(op.f("ix_memory_review_tasks_page_id"), "memory_review_tasks", ["page_id"], unique=False)
        op.create_index(op.f("ix_memory_review_tasks_status"), "memory_review_tasks", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    if sa.inspect(bind).has_table("memory_review_tasks"):
        op.drop_index(op.f("ix_memory_review_tasks_status"), table_name="memory_review_tasks")
        op.drop_index(op.f("ix_memory_review_tasks_page_id"), table_name="memory_review_tasks")
        op.drop_index(op.f("ix_memory_review_tasks_user_id"), table_name="memory_review_tasks")
        op.drop_table("memory_review_tasks")

    if sa.inspect(bind).has_table("memory_events"):
        op.drop_index(op.f("ix_memory_events_page_id"), table_name="memory_events")
        op.drop_index(op.f("ix_memory_events_user_id"), table_name="memory_events")
        op.drop_table("memory_events")

    if sa.inspect(bind).has_table("memory_links"):
        op.drop_index(op.f("ix_memory_links_to_page_id"), table_name="memory_links")
        op.drop_index(op.f("ix_memory_links_from_page_id"), table_name="memory_links")
        op.drop_index(op.f("ix_memory_links_user_id"), table_name="memory_links")
        op.drop_table("memory_links")

    if sa.inspect(bind).has_table("memory_sources"):
        op.drop_index(op.f("ix_memory_sources_user_id"), table_name="memory_sources")
        op.drop_index(op.f("ix_memory_sources_page_id"), table_name="memory_sources")
        op.drop_table("memory_sources")

    if sa.inspect(bind).has_table("memory_pages"):
        op.drop_index(op.f("ix_memory_pages_page_type"), table_name="memory_pages")
        op.drop_index(op.f("ix_memory_pages_status"), table_name="memory_pages")
        op.drop_index(op.f("ix_memory_pages_user_id"), table_name="memory_pages")
        op.drop_table("memory_pages")