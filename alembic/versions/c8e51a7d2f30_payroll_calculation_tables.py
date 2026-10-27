"""Persist payroll runs/items and configurable tax parameters.

Revision ID: c8e51a7d2f30
Revises: b7a98dc41e02
"""
from alembic import op
import sqlalchemy as sa

revision = "c8e51a7d2f30"
down_revision = "b7a98dc41e02"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("statutory_rates",
        sa.Column("parameter", sa.String(80), primary_key=True), sa.Column("effective_from", sa.Date(), primary_key=True),
        sa.Column("value", sa.Numeric(18, 4), nullable=False), sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("note", sa.String(500), nullable=False))
    op.create_table("tax_parameters", sa.Column("parameter", sa.String(80), primary_key=True),
        sa.Column("value", sa.Numeric(18, 4), nullable=False), sa.Column("note", sa.String(500), nullable=False))
    op.create_table("tax_slabs", sa.Column("slab_id", sa.String(20), primary_key=True),
        sa.Column("regime", sa.String(20), nullable=False), sa.Column("financial_year", sa.String(12), nullable=False),
        sa.Column("income_from", sa.Numeric(18, 2), nullable=False), sa.Column("income_to", sa.Numeric(18, 2), nullable=False),
        sa.Column("rate_percent", sa.Numeric(8, 4), nullable=False), sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("note", sa.String(500), nullable=False))
    op.create_index("ix_tax_slabs_financial_year", "tax_slabs", ["financial_year"])
    op.create_index("ix_tax_slabs_fy_regime_from", "tax_slabs", ["financial_year", "regime", "income_from"])
    op.create_table("payroll_runs", sa.Column("run_id", sa.String(30), primary_key=True),
        sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=False), sa.Column("employees_paid", sa.Integer(), nullable=False),
        sa.Column("total_gross", sa.Numeric(18, 2), nullable=False), sa.Column("total_deductions", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_net", sa.Numeric(18, 2), nullable=False), sa.Column("total_employer_contributions", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_employer_cost", sa.Numeric(18, 2), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("run_by", sa.String(30)), sa.Column("approved_by", sa.String(30)), sa.Column("created_at", sa.DateTime()),
        sa.Column("approved_at", sa.DateTime()), sa.Column("idempotency_key", sa.String(100), unique=True),
        sa.Column("journal_entry_id", sa.String(30)), sa.Column("calculation_version", sa.String(50), nullable=False))
    op.create_index("ix_payroll_runs_status", "payroll_runs", ["status"])
    op.create_table("payroll_items", sa.Column("payroll_item_id", sa.String(30), primary_key=True),
        sa.Column("run_id", sa.String(30), sa.ForeignKey("payroll_runs.run_id"), nullable=False),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("department_id", sa.String(10), nullable=False), sa.Column("role_id", sa.String(10), nullable=False),
        sa.Column("calendar_days", sa.Integer(), nullable=False), sa.Column("days_employed", sa.Integer(), nullable=False),
        *[sa.Column(c, sa.Numeric(18 if c not in ("lop_days", "payable_days", "overtime_hours_paid") else 8, 2), nullable=False) for c in (
          "lop_days","payable_days","monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance",
          "earned_fixed_pay","overtime_hours_paid","overtime_pay","variable_pay")],
        sa.Column("variable_pay_type", sa.String(50)), sa.Column("gross_pay", sa.Numeric(18,2), nullable=False),
        *[sa.Column(c, sa.Numeric(18,2), nullable=False) for c in ("pf_employee","esi_employee","professional_tax","tds","other_deductions","total_deductions","net_pay","pf_employer","esi_employer","employer_cost")],
        sa.Column("calculation_note", sa.String(500)),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_payroll_run_employee"))
    op.create_index("ix_payroll_items_run_id", "payroll_items", ["run_id"])
    op.create_index("ix_payroll_items_employee_id", "payroll_items", ["employee_id"])

def downgrade() -> None:
    op.drop_index("ix_payroll_items_employee_id", table_name="payroll_items")
    op.drop_index("ix_payroll_items_run_id", table_name="payroll_items")
    op.drop_table("payroll_items")
    op.drop_index("ix_payroll_runs_status", table_name="payroll_runs")
    op.drop_table("payroll_runs")
    op.drop_index("ix_tax_slabs_fy_regime_from", table_name="tax_slabs")
    op.drop_index("ix_tax_slabs_financial_year", table_name="tax_slabs")
    op.drop_table("tax_slabs"); op.drop_table("tax_parameters"); op.drop_table("statutory_rates")
