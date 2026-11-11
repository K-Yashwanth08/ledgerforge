"""Allow pending payroll snapshots without a pay date."""
from alembic import op
import sqlalchemy as sa

revision = "d9f02b6c7a11"
down_revision = "c8e51a7d2f30"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("payroll_runs") as batch:
        batch.alter_column("pay_date", existing_type=sa.Date(), nullable=True)

def downgrade() -> None:
    raise RuntimeError("Cannot make pay_date required while imported pending payroll rows have no pay date")
