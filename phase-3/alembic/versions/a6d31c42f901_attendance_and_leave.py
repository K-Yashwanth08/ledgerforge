"""Add attendance, holidays, leave types, balances and requests.

Revision ID: a6d31c42f901
Revises: fbedb25799e5
"""
from alembic import op
import sqlalchemy as sa

revision = "a6d31c42f901"
down_revision = "fbedb25799e5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("leave_types",
        sa.Column("leave_type_code", sa.String(10), primary_key=True),
        sa.Column("leave_type_name", sa.String(100), nullable=False),
        sa.Column("pay_type", sa.String(20), nullable=False),
        sa.Column("annual_quota_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("prorated_for_joiners", sa.Boolean(), nullable=False),
        sa.Column("carry_forward_allowed", sa.Boolean(), nullable=False),
        sa.Column("max_carry_forward_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("policy_note", sa.String(500)))
    op.create_table("holidays",
        sa.Column("holiday_date", sa.Date(), primary_key=True),
        sa.Column("holiday_name", sa.String(150), nullable=False),
        sa.Column("holiday_type", sa.String(30), nullable=False),
        sa.Column("weekday", sa.String(12), nullable=False),
        sa.Column("falls_on_weekend", sa.Boolean(), nullable=False),
        sa.Column("calendar_note", sa.String(300)))
    op.create_table("attendance_records",
        sa.Column("attendance_id", sa.String(24), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(12), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("leave_type_code", sa.String(10)),
        sa.Column("check_in", sa.Time()), sa.Column("check_out", sa.Time()),
        sa.Column("hours_worked", sa.Numeric(6, 2)), sa.Column("overtime_hours", sa.Numeric(6, 2)),
        sa.Column("late_flag", sa.String(1)), sa.Column("source", sa.String(30)),
        sa.Column("data_quality_flag", sa.String(40)),
        sa.Column("department_id", sa.String(10), sa.ForeignKey("departments.department_id")),
        sa.UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"))
    op.create_index("ix_attendance_records_employee_id", "attendance_records", ["employee_id"])
    op.create_index("ix_attendance_records_attendance_date", "attendance_records", ["attendance_date"])
    op.create_index("ix_attendance_records_status", "attendance_records", ["status"])
    op.create_index("ix_attendance_records_department_id", "attendance_records", ["department_id"])
    op.create_table("leave_balances",
        sa.Column("balance_id", sa.String(30), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("leave_type_code", sa.String(10), sa.ForeignKey("leave_types.leave_type_code"), nullable=False),
        sa.Column("financial_year", sa.String(12), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("entitlement_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("used_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("balance_days", sa.Numeric(7, 2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("entitlement_days >= 0 AND used_days >= 0 AND balance_days >= 0", name="ck_leave_balance_nonnegative"),
        sa.UniqueConstraint("employee_id", "leave_type_code", "financial_year", name="uq_leave_balance_employee_type_fy"))
    op.create_index("ix_leave_balances_employee_id", "leave_balances", ["employee_id"])
    op.create_index("ix_leave_balances_leave_type_code", "leave_balances", ["leave_type_code"])
    op.create_table("leave_requests",
        sa.Column("leave_request_id", sa.String(30), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("leave_type_code", sa.String(10), sa.ForeignKey("leave_types.leave_type_code"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Numeric(7, 2), nullable=False), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("approver_id", sa.String(30)), sa.Column("decided_on", sa.Date()),
        sa.Column("is_half_day", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_leave_requests_employee_id", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_requests_leave_type_code", "leave_requests", ["leave_type_code"])
    op.create_index("ix_leave_requests_start_date", "leave_requests", ["start_date"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])

def downgrade() -> None:
    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_start_date", table_name="leave_requests")
    op.drop_index("ix_leave_requests_leave_type_code", table_name="leave_requests")
    op.drop_index("ix_leave_requests_employee_id", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_index("ix_leave_balances_leave_type_code", table_name="leave_balances")
    op.drop_index("ix_leave_balances_employee_id", table_name="leave_balances")
    op.drop_table("leave_balances")
    op.drop_index("ix_attendance_records_department_id", table_name="attendance_records")
    op.drop_index("ix_attendance_records_status", table_name="attendance_records")
    op.drop_index("ix_attendance_records_attendance_date", table_name="attendance_records")
    op.drop_index("ix_attendance_records_employee_id", table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_table("holidays")
    op.drop_table("leave_types")
