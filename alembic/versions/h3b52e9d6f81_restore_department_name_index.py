"""Restore the unique department-name index represented in model metadata."""
from alembic import op

revision = "h3b52e9d6f81"
down_revision = "g2a41d8c5e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_departments_department_name", "departments", ["department_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_departments_department_name", table_name="departments")
