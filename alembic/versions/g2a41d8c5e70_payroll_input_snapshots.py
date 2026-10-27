"""Persist payroll calculation inputs for historical audit and replay."""
from alembic import op
import sqlalchemy as sa

revision = "g2a41d8c5e70"
down_revision = "f1c7a94b2e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_items", sa.Column("calculation_input_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payroll_items", "calculation_input_snapshot")
