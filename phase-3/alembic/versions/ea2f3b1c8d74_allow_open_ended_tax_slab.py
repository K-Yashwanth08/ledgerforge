"""Allow tax slabs with no upper-income bound."""
from alembic import op
import sqlalchemy as sa

revision = "ea2f3b1c8d74"
down_revision = "d9f02b6c7a11"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("tax_slabs") as batch:
        batch.alter_column("income_to", existing_type=sa.Numeric(18,2), nullable=True)

def downgrade() -> None:
    raise RuntimeError("Cannot mark an open-ended tax slab as bounded without inventing an upper limit")
