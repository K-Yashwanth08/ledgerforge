"""Add explicit payroll payment and reversal references."""
from alembic import op
import sqlalchemy as sa

revision = "j5a8f2c61d40"
down_revision = "i4c63e8a91bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    present = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("payroll_runs")}
    for name in ("payment_journal_entry_id", "reversal_entry_id", "payment_reversal_entry_id"):
        if name not in present:
            op.add_column("payroll_runs", sa.Column(name, sa.String(30), nullable=True))
    op.create_table("payroll_payments",
        sa.Column("payment_id", sa.String(40), primary_key=True),
        sa.Column("run_id", sa.String(30), sa.ForeignKey("payroll_runs.run_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("bank_account_code", sa.String(20), sa.ForeignKey("chart_of_accounts.account_code"), nullable=False),
        sa.Column("payment_mode", sa.String(40)), sa.Column("reference_no", sa.String(100)),
        sa.Column("ledger_entry_id", sa.String(30), sa.ForeignKey("journal_entries.entry_id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("created_by", sa.String(30)),
        sa.UniqueConstraint("run_id", name="uq_payroll_payment_run"),
        sa.UniqueConstraint("ledger_entry_id", name="uq_payroll_payment_journal"),
        sa.UniqueConstraint("idempotency_key", name="uq_payroll_payment_idempotency"))
    op.create_index("ix_payroll_payments_run_id", "payroll_payments", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_payroll_payments_run_id", table_name="payroll_payments")
    op.drop_table("payroll_payments")
    op.drop_column("payroll_runs", "payment_reversal_entry_id")
    op.drop_column("payroll_runs", "reversal_entry_id")
    op.drop_column("payroll_runs", "payment_journal_entry_id")
