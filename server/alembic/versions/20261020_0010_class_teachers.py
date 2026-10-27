"""Allow multiple teachers to manage a class."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261020_0010"
down_revision = "20260926_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_teachers",
        sa.Column("class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("class_teachers")
