"""Add vendor bills, approval history, and payments."""
from alembic import op
import sqlalchemy as sa

revision = "i4c63e8a91bd"
down_revision = "h3b52e9d6f81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_journal_expense_source", "journal_entries", ["source_id"], unique=True,
        sqlite_where=sa.text("source_type = 'EXPENSE' AND source_id IS NOT NULL"),
        postgresql_where=sa.text("source_type = 'EXPENSE' AND source_id IS NOT NULL"))
    op.create_index("uq_journal_expense_payment_source", "journal_entries", ["source_id"], unique=True,
        sqlite_where=sa.text("source_type = 'EXPENSE_PAYMENT' AND source_id IS NOT NULL"),
        postgresql_where=sa.text("source_type = 'EXPENSE_PAYMENT' AND source_id IS NOT NULL"))
    op.create_table("vendors",
        sa.Column("vendor_id", sa.String(30), primary_key=True),
        sa.Column("vendor_name", sa.String(200), nullable=False),
        sa.Column("primary_expense_account", sa.String(20), sa.ForeignKey("chart_of_accounts.account_code"), nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(100)), sa.Column("gst_registration", sa.String(40)),
        sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_index("ix_vendors_vendor_name", "vendors", ["vendor_name"])
    op.create_index("ix_vendors_is_active", "vendors", ["is_active"])

    op.create_table("expense_bills",
        sa.Column("expense_id", sa.String(40), primary_key=True),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category_account", sa.String(20), sa.ForeignKey("chart_of_accounts.account_code"), nullable=False),
        sa.Column("vendor_id", sa.String(30), sa.ForeignKey("vendors.vendor_id"), nullable=False),
        sa.Column("bill_reference", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("department_id", sa.String(10), sa.ForeignKey("departments.department_id")),
        sa.Column("amount_excl_gst", sa.Numeric(18, 2), nullable=False),
        sa.Column("gst_rate_percent", sa.Numeric(7, 4), nullable=False),
        sa.Column("gst_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False), sa.Column("paid_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("source_status", sa.String(20)),
        sa.Column("payment_mode", sa.String(40)), sa.Column("submitted_by", sa.String(40), nullable=False),
        sa.Column("approved_by", sa.String(40)), sa.Column("approved_at", sa.DateTime()),
        sa.Column("ledger_entry_id", sa.String(30), sa.ForeignKey("journal_entries.entry_id")),
        sa.Column("payment_ledger_entry_id", sa.String(30), sa.ForeignKey("journal_entries.entry_id")),
        sa.Column("legacy_sod_violation", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount_excl_gst >= 0 AND gst_amount >= 0 AND total_amount >= 0", name="ck_expense_bill_nonnegative"),
        sa.CheckConstraint("total_amount = amount_excl_gst + gst_amount", name="ck_expense_bill_total"))
    for col in ("expense_date", "vendor_id", "bill_reference", "due_date", "status"):
        op.create_index(f"ix_expense_bills_{col}", "expense_bills", [col])

    op.create_table("expense_approval_history",
        sa.Column("history_id", sa.String(40), primary_key=True),
        sa.Column("expense_id", sa.String(40), sa.ForeignKey("expense_bills.expense_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime()),
        sa.Column("legacy_import", sa.Boolean(), nullable=False))
    op.create_index("ix_expense_approval_history_expense_id", "expense_approval_history", ["expense_id"])

    op.create_table("expense_payments",
        sa.Column("payment_id", sa.String(40), primary_key=True),
        sa.Column("expense_id", sa.String(40), sa.ForeignKey("expense_bills.expense_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("cash_account_code", sa.String(20), sa.ForeignKey("chart_of_accounts.account_code"), nullable=False),
        sa.Column("payment_mode", sa.String(40), nullable=False),
        sa.Column("reference_no", sa.String(100)),
        sa.Column("ledger_entry_id", sa.String(30), sa.ForeignKey("journal_entries.entry_id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.UniqueConstraint("expense_id", name="uq_expense_payment_bill"),
        sa.UniqueConstraint("idempotency_key", name="uq_expense_payment_idempotency"))
    op.create_index("ix_expense_payments_expense_id", "expense_payments", ["expense_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_payments_expense_id", table_name="expense_payments")
    op.drop_table("expense_payments")
    op.drop_index("ix_expense_approval_history_expense_id", table_name="expense_approval_history")
    op.drop_table("expense_approval_history")
    for col in ("status", "due_date", "bill_reference", "vendor_id", "expense_date"):
        op.drop_index(f"ix_expense_bills_{col}", table_name="expense_bills")
    op.drop_table("expense_bills")
    op.drop_index("ix_vendors_is_active", table_name="vendors")
    op.drop_index("ix_vendors_vendor_name", table_name="vendors")
    op.drop_table("vendors")
    op.drop_index("uq_journal_expense_payment_source", table_name="journal_entries")
    op.drop_index("uq_journal_expense_source", table_name="journal_entries")
