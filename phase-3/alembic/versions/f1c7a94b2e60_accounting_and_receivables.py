"""Add immutable journal, chart of accounts, clients and receivables."""
from alembic import op
import sqlalchemy as sa

revision = "f1c7a94b2e60"
down_revision = "ea2f3b1c8d74"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("chart_of_accounts",
        sa.Column("account_code",sa.String(20),primary_key=True),sa.Column("account_name",sa.String(150),nullable=False),
        sa.Column("account_type",sa.String(20),nullable=False),sa.Column("normal_balance",sa.String(10),nullable=False),
        sa.Column("parent_code",sa.String(20),sa.ForeignKey("chart_of_accounts.account_code")),
        sa.Column("is_group",sa.Boolean(),nullable=False),sa.Column("statement",sa.String(30),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False))
    op.create_index("ix_chart_of_accounts_account_type","chart_of_accounts",["account_type"])
    op.create_index("ix_chart_of_accounts_parent_code","chart_of_accounts",["parent_code"])
    op.create_table("journal_entries",
        sa.Column("entry_id",sa.String(30),primary_key=True),sa.Column("entry_date",sa.Date(),nullable=False),
        sa.Column("posting_period",sa.String(10),nullable=False),sa.Column("financial_year",sa.String(12),nullable=False),
        sa.Column("description",sa.String(500),nullable=False),sa.Column("source_type",sa.String(40),nullable=False),
        sa.Column("source_id",sa.String(40)),sa.Column("status",sa.String(20),nullable=False),
        sa.Column("total_debit",sa.Numeric(18,2),nullable=False),sa.Column("total_credit",sa.Numeric(18,2),nullable=False),
        sa.Column("reversal_of_source_id",sa.String(40)),sa.Column("created_by",sa.String(30)),sa.Column("created_at",sa.DateTime()))
    for col in ("entry_date","posting_period","financial_year","source_type","source_id","status"):
        op.create_index(f"ix_journal_entries_{col}","journal_entries",[col])
    op.create_table("journal_lines",
        sa.Column("line_id",sa.String(30),primary_key=True),sa.Column("entry_id",sa.String(30),sa.ForeignKey("journal_entries.entry_id",ondelete="RESTRICT"),nullable=False),
        sa.Column("line_no",sa.Integer(),nullable=False),sa.Column("account_code",sa.String(20),sa.ForeignKey("chart_of_accounts.account_code"),nullable=False),
        sa.Column("debit",sa.Numeric(18,2),nullable=False),sa.Column("credit",sa.Numeric(18,2),nullable=False),
        sa.Column("cost_center_department_id",sa.String(10),sa.ForeignKey("departments.department_id")),sa.Column("line_description",sa.String(500),nullable=False),
        sa.CheckConstraint("debit >= 0 AND credit >= 0 AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))",name="ck_journal_line_one_positive_side"),
        sa.UniqueConstraint("entry_id","line_no",name="uq_journal_line_number"))
    op.create_index("ix_journal_lines_entry_id","journal_lines",["entry_id"])
    op.create_index("ix_journal_lines_account_code","journal_lines",["account_code"])
    op.create_table("clients",
        sa.Column("client_id",sa.String(20),primary_key=True),sa.Column("client_name",sa.String(200),nullable=False),
        sa.Column("industry",sa.String(100)),sa.Column("city",sa.String(100)),sa.Column("state_or_region",sa.String(100)),
        sa.Column("country",sa.String(80),nullable=False),sa.Column("client_type",sa.String(50)),sa.Column("gst_registration",sa.String(30)),
        sa.Column("payment_terms_days",sa.Integer(),nullable=False),sa.Column("payment_behaviour",sa.String(100)),
        sa.Column("primary_service_line",sa.String(100)),sa.Column("contact_email",sa.String(255)),sa.Column("onboarded_on",sa.Date()),
        sa.Column("is_active",sa.Boolean(),nullable=False))
    op.create_index("ix_clients_client_name","clients",["client_name"])
    op.create_index("ix_clients_is_active","clients",["is_active"])
    op.create_table("invoices",
        sa.Column("invoice_id",sa.String(30),primary_key=True),sa.Column("invoice_number",sa.String(40),nullable=False),
        sa.Column("client_id",sa.String(20),sa.ForeignKey("clients.client_id"),nullable=False),sa.Column("invoice_date",sa.Date(),nullable=False),
        sa.Column("due_date",sa.Date(),nullable=False),sa.Column("service_line_account",sa.String(20),sa.ForeignKey("chart_of_accounts.account_code"),nullable=False),
        sa.Column("currency",sa.String(3),nullable=False),sa.Column("subtotal",sa.Numeric(18,2),nullable=False),
        sa.Column("gst_rate_percent",sa.Numeric(7,4),nullable=False),sa.Column("gst_amount",sa.Numeric(18,2),nullable=False),
        sa.Column("total_amount",sa.Numeric(18,2),nullable=False),sa.Column("amount_paid",sa.Numeric(18,2),nullable=False),
        sa.Column("balance_due",sa.Numeric(18,2),nullable=False),sa.Column("status",sa.String(24),nullable=False),
        sa.Column("last_payment_date",sa.Date()),sa.Column("po_number",sa.String(60)),sa.Column("carried_in_from_prior_period",sa.Boolean(),nullable=False),
        sa.Column("created_by",sa.String(30)),sa.Column("created_at",sa.DateTime()),sa.Column("ledger_entry_id",sa.String(30),sa.ForeignKey("journal_entries.entry_id")))
    op.create_index("ix_invoices_invoice_number","invoices",["invoice_number"],unique=True)
    for col in ("client_id","invoice_date","due_date","status"):
        op.create_index(f"ix_invoices_{col}","invoices",[col])
    op.create_table("invoice_items",
        sa.Column("invoice_item_id",sa.String(30),primary_key=True),sa.Column("invoice_id",sa.String(30),sa.ForeignKey("invoices.invoice_id",ondelete="RESTRICT"),nullable=False),
        sa.Column("line_no",sa.Integer(),nullable=False),sa.Column("description",sa.String(500),nullable=False),
        sa.Column("quantity",sa.Numeric(12,3),nullable=False),sa.Column("unit_price",sa.Numeric(18,2),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("revenue_account",sa.String(20),sa.ForeignKey("chart_of_accounts.account_code"),nullable=False),
        sa.UniqueConstraint("invoice_id","line_no",name="uq_invoice_item_line"))
    op.create_index("ix_invoice_items_invoice_id","invoice_items",["invoice_id"])
    op.create_table("invoice_payments",
        sa.Column("payment_id",sa.String(30),primary_key=True),sa.Column("invoice_id",sa.String(30),sa.ForeignKey("invoices.invoice_id",ondelete="RESTRICT"),nullable=False),
        sa.Column("payment_date",sa.Date(),nullable=False),sa.Column("amount",sa.Numeric(18,2),nullable=False),
        sa.Column("payment_mode",sa.String(40),nullable=False),sa.Column("reference_no",sa.String(100)),sa.Column("received_by",sa.String(30)),
        sa.Column("ledger_entry_id",sa.String(30),sa.ForeignKey("journal_entries.entry_id")),sa.Column("idempotency_key",sa.String(100),unique=True))
    op.create_index("ix_invoice_payments_invoice_id","invoice_payments",["invoice_id"])

def downgrade() -> None:
    op.drop_index("ix_invoice_payments_invoice_id",table_name="invoice_payments"); op.drop_table("invoice_payments")
    op.drop_index("ix_invoice_items_invoice_id",table_name="invoice_items"); op.drop_table("invoice_items")
    for col in ("status","due_date","invoice_date","client_id"):op.drop_index(f"ix_invoices_{col}",table_name="invoices")
    op.drop_table("invoices"); op.drop_index("ix_clients_is_active",table_name="clients"); op.drop_index("ix_clients_client_name",table_name="clients"); op.drop_table("clients")
    op.drop_index("ix_journal_lines_account_code",table_name="journal_lines"); op.drop_index("ix_journal_lines_entry_id",table_name="journal_lines"); op.drop_table("journal_lines")
    for col in ("status","source_id","source_type","financial_year","posting_period","entry_date"):op.drop_index(f"ix_journal_entries_{col}",table_name="journal_entries")
    op.drop_table("journal_entries"); op.drop_index("ix_chart_of_accounts_parent_code",table_name="chart_of_accounts"); op.drop_index("ix_chart_of_accounts_account_type",table_name="chart_of_accounts"); op.drop_table("chart_of_accounts")
