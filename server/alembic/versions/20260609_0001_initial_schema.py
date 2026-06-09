"""initial schema

Revision ID: 20260609_0001
Revises:
Create Date: 2026-06-09
"""

from alembic import op

from app.models import Base

revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
