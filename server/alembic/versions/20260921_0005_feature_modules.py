"""add feature modules

Revision ID: 20260921_0005
Revises: 20260921_0004
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260921_0005"
down_revision = "20260921_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not sa.inspect(bind).has_table("feature_modules"):
        op.create_table(
            "feature_modules",
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("visible", sa.Boolean(), nullable=False),
            sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_feature_modules_code"),
        )
        op.create_index(op.f("ix_feature_modules_code"), "feature_modules", ["code"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    if sa.inspect(bind).has_table("feature_modules"):
        op.drop_index(op.f("ix_feature_modules_code"), table_name="feature_modules")
        op.drop_table("feature_modules")