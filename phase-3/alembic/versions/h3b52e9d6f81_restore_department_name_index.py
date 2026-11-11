"""Restore the unique department-name index represented in model metadata."""
from alembic import op
import sqlalchemy as sa

revision = "h3b52e9d6f81"
down_revision = "g2a41d8c5e70"
branch_labels = None
depends_on = None


def _ensure_department_name_index() -> None:
    # The initial migration owns this unique index. Older upgraded databases
    # may lack it, so restore it only when absent and replace an incompatible
    # same-named index if necessary.
    indexes = sa.inspect(op.get_bind()).get_indexes("departments")
    existing = next((index for index in indexes
                     if index.get("name") == "ix_departments_department_name"), None)
    if existing and existing.get("unique") and existing.get("column_names") == ["department_name"]:
        return
    if existing:
        op.drop_index("ix_departments_department_name", table_name="departments")
    op.create_index("ix_departments_department_name", "departments", ["department_name"], unique=True)


def upgrade() -> None:
    _ensure_department_name_index()


def downgrade() -> None:
    # This revision repairs an index owned by the initial schema migration.
    # Keep the base-schema invariant when downgrading to that earlier revision.
    _ensure_department_name_index()
