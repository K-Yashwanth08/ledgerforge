"""Make tax parameters, slabs and statutory rates effective dated."""
from alembic import op
import sqlalchemy as sa

revision = "l7e4a2c9d610"
down_revision = "k6d9e31a4b72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep legacy rows, but label their supplied sample policy explicitly.
    with op.batch_alter_table("tax_parameters", naming_convention={"pk": "pk_%(table_name)s"}) as batch:
        batch.add_column(sa.Column("financial_year", sa.String(12), nullable=False, server_default="FY2025-26"))
        batch.add_column(sa.Column("regime", sa.String(20), nullable=False, server_default="NEW"))
        batch.add_column(sa.Column("effective_from", sa.Date(), nullable=False, server_default="1900-01-01"))
        batch.add_column(sa.Column("effective_to", sa.Date(), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.drop_constraint("pk_tax_parameters", type_="primary")
        batch.create_primary_key("pk_tax_parameters", ["parameter", "financial_year", "regime", "effective_from"])
    for table in ("tax_slabs", "statutory_rates"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("effective_to", sa.Date(), nullable=True))
            batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
            batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
            batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_tax_parameters_lookup", "tax_parameters",
                    ["financial_year", "regime", "parameter", "effective_from"])
    op.create_index("ix_statutory_rates_lookup", "statutory_rates", ["parameter", "effective_from"])


def downgrade() -> None:
    raise RuntimeError("Effective-dated tax data cannot be safely downgraded without discarding configurations")
