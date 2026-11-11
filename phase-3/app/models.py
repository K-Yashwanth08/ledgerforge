from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Department(Base):
    __tablename__ = "departments"
    department_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    cost_center: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    roles: Mapped[list["Role"]] = relationship(back_populates="department")

class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"), index=True)
    role_title: Mapped[str] = mapped_column(String(150))
    level: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(100))
    band_min_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    band_mid_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    band_max_annual: Mapped[float] = mapped_column(Numeric(12, 2))
    overtime_eligible: Mapped[str] = mapped_column(String(1))
    band_year: Mapped[int] = mapped_column(Integer)
    department: Mapped[Department] = relationship(back_populates="roles")

class Employee(Base):
    __tablename__ = "employees"
    employee_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(201), index=True)
    work_email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    hire_date: Mapped[date] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(String(30), index=True)
    employment_type: Mapped[str] = mapped_column(String(30))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"), index=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), index=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True, index=True)
    work_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    highest_education: Mapped[str | None] = mapped_column(String(150), nullable=True)
    prior_experience_years: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    career_gap_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commute_distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    pf_applicable: Mapped[str | None] = mapped_column(String(1), nullable=True)
    esi_applicable: Mapped[str | None] = mapped_column(String(1), nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resignation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[Department] = relationship()
    role: Mapped[Role] = relationship()
    manager: Mapped["Employee | None"] = relationship(remote_side="Employee.employee_id", foreign_keys=[manager_id])

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("role IN ('Admin', 'HR', 'Employee')", name="ck_users_role"),
    )

class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"
    assignment_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.department_id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"))
    job_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    component_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    component_name: Mapped[str] = mapped_column(String(120), unique=True)
    component_type: Mapped[str] = mapped_column(String(40), index=True)
    taxable: Mapped[bool] = mapped_column(default=False)
    calculation_rule: Mapped[str] = mapped_column(String(500))
    is_fixed: Mapped[bool] = mapped_column(default=False)
    structures: Mapped[list["SalaryStructure"]] = relationship(back_populates="component")

class SalaryRevision(Base):
    __tablename__ = "salary_revisions"
    revision_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    revision_reason: Mapped[str] = mapped_column(String(200))
    previous_annual_fixed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    new_annual_fixed: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    role_id_after: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[date] = mapped_column(Date)
    __table_args__ = (CheckConstraint("new_annual_fixed >= 0", name="ck_salary_revision_new_nonnegative"),)

class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    structure_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("salary_components.component_id"), index=True)
    component_name: Mapped[str] = mapped_column(String(120))  # source snapshot
    component_type: Mapped[str] = mapped_column(String(40))  # source snapshot
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("salary_revisions.revision_id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    component: Mapped[SalaryComponent] = relationship(back_populates="structures")
    __table_args__ = (
        CheckConstraint("monthly_amount >= 0", name="ck_salary_structure_nonnegative"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from OR is_active = 0", name="ck_salary_structure_dates"),
        Index("ix_salary_structure_lookup", "employee_id", "effective_from", "effective_to", "is_active"),
        Index("uq_active_salary_component_start", "employee_id", "component_id", "effective_from", unique=True,
              sqlite_where=text("is_active = 1"), postgresql_where=text("is_active")),
    )

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    attendance_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    attendance_date: Mapped[date] = mapped_column(Date, index=True)
    weekday: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(30), index=True)
    leave_type_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    check_in: Mapped[str | None] = mapped_column(String(12), nullable=True)
    check_out: Mapped[str | None] = mapped_column(String(12), nullable=True)
    hours_worked: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    overtime_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    late_flag: Mapped[str | None] = mapped_column(String(1), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data_quality_flag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.department_id"), nullable=True, index=True)
    __table_args__ = (UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),)

class LeaveType(Base):
    __tablename__ = "leave_types"
    leave_type_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    leave_type_name: Mapped[str] = mapped_column(String(100))
    pay_type: Mapped[str] = mapped_column(String(20))
    annual_quota_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    prorated_for_joiners: Mapped[bool] = mapped_column(default=False)
    carry_forward_allowed: Mapped[bool] = mapped_column(default=False)
    max_carry_forward_days: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=0)
    policy_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

class LeaveBalance(Base):
    __tablename__ = "leave_balances"
    balance_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    leave_type_code: Mapped[str] = mapped_column(ForeignKey("leave_types.leave_type_code"), index=True)
    financial_year: Mapped[str] = mapped_column(String(12))
    as_of_date: Mapped[date] = mapped_column(Date)
    entitlement_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    used_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    balance_days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_code", "financial_year", name="uq_leave_balance_employee_type_fy"),
        CheckConstraint("entitlement_days >= 0 AND used_days >= 0 AND balance_days >= 0", name="ck_leave_balance_nonnegative"),
    )

class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    leave_request_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    leave_type_code: Mapped[str] = mapped_column(ForeignKey("leave_types.leave_type_code"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), index=True)
    applied_on: Mapped[date] = mapped_column(Date)
    approver_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    decided_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_half_day: Mapped[bool] = mapped_column(default=False, nullable=False)

class Holiday(Base):
    __tablename__ = "holidays"
    holiday_date: Mapped[date] = mapped_column(Date, primary_key=True)
    holiday_name: Mapped[str] = mapped_column(String(150))
    holiday_type: Mapped[str] = mapped_column(String(30))
    weekday: Mapped[str] = mapped_column(String(12))
    falls_on_weekend: Mapped[bool] = mapped_column(default=False)
    calendar_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

class StatutoryRate(Base):
    __tablename__ = "statutory_rates"
    parameter: Mapped[str] = mapped_column(String(80), primary_key=True)
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(String(500))
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class TaxParameter(Base):
    __tablename__ = "tax_parameters"
    parameter: Mapped[str] = mapped_column(String(80), primary_key=True)
    financial_year: Mapped[str] = mapped_column(String(12), primary_key=True, default="FY2025-26")
    regime: Mapped[str] = mapped_column(String(20), primary_key=True, default="NEW")
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True, default=date(1900, 1, 1))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    note: Mapped[str] = mapped_column(String(500))
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class TaxSlab(Base):
    __tablename__ = "tax_slabs"
    slab_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    regime: Mapped[str] = mapped_column(String(20))
    financial_year: Mapped[str] = mapped_column(String(12), index=True)
    income_from: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    income_to: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    effective_from: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(500))
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_tax_slabs_fy_regime_from", "financial_year", "regime", "income_from"),)

class EmployeeTaxElection(Base):
    __tablename__ = "employee_tax_elections"
    election_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    financial_year: Mapped[str] = mapped_column(String(12), index=True)
    regime: Mapped[str] = mapped_column(String(20))
    election_date: Mapped[date] = mapped_column(Date)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    __table_args__ = (
        CheckConstraint("approval_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_tax_election_status"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_tax_election_dates"),
        Index("ix_tax_elections_employee_period", "employee_id", "financial_year", "effective_from"),
    )

class EmployeeTaxDeclaration(Base):
    __tablename__ = "employee_tax_declarations"
    declaration_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    financial_year: Mapped[str] = mapped_column(String(12), index=True)
    deduction_code: Mapped[str] = mapped_column(String(60))
    declared_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    supporting_document_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    __table_args__ = (
        CheckConstraint("declared_amount >= 0", name="ck_tax_declaration_amount"),
        CheckConstraint("approval_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_tax_declaration_status"),
        Index("ix_tax_declarations_employee_fy", "employee_id", "financial_year"),
    )

class EmployeeTaxAuditEvent(Base):
    __tablename__ = "employee_tax_audit_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    run_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employees_paid: Mapped[int] = mapped_column(Integer)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_net: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_employer_contributions: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_employer_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(40), index=True)
    run_by: Mapped[str | None] = mapped_column(String(30))
    approved_by: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    journal_entry_id: Mapped[str | None] = mapped_column(String(30))
    payment_journal_entry_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reversal_entry_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payment_reversal_entry_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(50))

class PayrollItem(Base):
    __tablename__ = "payroll_items"
    payroll_item_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.run_id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.employee_id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    department_id: Mapped[str] = mapped_column(String(10))
    role_id: Mapped[str] = mapped_column(String(10))
    calendar_days: Mapped[int] = mapped_column(Integer)
    days_employed: Mapped[int] = mapped_column(Integer)
    lop_days: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    payable_days: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    monthly_fixed_gross: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    basic: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    hra: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    conveyance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    medical: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    special_allowance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    earned_fixed_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    overtime_hours_paid: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    overtime_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    variable_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    variable_pay_type: Mapped[str | None] = mapped_column(String(50))
    gross_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    pf_employee: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    esi_employee: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    professional_tax: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tds: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    net_pay: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    pf_employer: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    esi_employer: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    employer_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    calculation_note: Mapped[str | None] = mapped_column(String(500))
    calculation_input_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("run_id", "employee_id", name="uq_payroll_run_employee"),)

class PayrollPayment(Base):
    __tablename__ = "payroll_payments"
    payment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.run_id", ondelete="RESTRICT"), unique=True, index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    bank_account_code: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    payment_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ledger_entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.entry_id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    created_by: Mapped[str | None] = mapped_column(String(30), nullable=True)

class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    account_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), index=True)
    normal_balance: Mapped[str] = mapped_column(String(10))
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("chart_of_accounts.account_code"), nullable=True, index=True)
    is_group: Mapped[bool] = mapped_column(default=False)
    statement: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(default=True)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    entry_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    posting_period: Mapped[str] = mapped_column(String(10), index=True)
    financial_year: Mapped[str] = mapped_column(String(12), index=True)
    description: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str | None] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reversal_of_source_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (
        Index("uq_journal_expense_source", "source_id", unique=True,
              sqlite_where=text("source_type = 'EXPENSE' AND source_id IS NOT NULL"),
              postgresql_where=text("source_type = 'EXPENSE' AND source_id IS NOT NULL")),
        Index("uq_journal_expense_payment_source", "source_id", unique=True,
              sqlite_where=text("source_type = 'EXPENSE_PAYMENT' AND source_id IS NOT NULL"),
              postgresql_where=text("source_type = 'EXPENSE_PAYMENT' AND source_id IS NOT NULL")),
    )

class JournalLine(Base):
    __tablename__ = "journal_lines"
    line_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.entry_id", ondelete="RESTRICT"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    account_code: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"), index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cost_center_department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.department_id"), nullable=True)
    line_description: Mapped[str] = mapped_column(String(500))
    __table_args__ = (UniqueConstraint("entry_id", "line_no", name="uq_journal_line_number"),
        CheckConstraint("debit >= 0 AND credit >= 0 AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))", name="ck_journal_line_one_positive_side"))

class Client(Base):
    __tablename__ = "clients"
    client_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    client_name: Mapped[str] = mapped_column(String(200), index=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    state_or_region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(80))
    client_type: Mapped[str | None] = mapped_column(String(50))
    gst_registration: Mapped[str | None] = mapped_column(String(30))
    payment_terms_days: Mapped[int] = mapped_column(Integer)
    payment_behaviour: Mapped[str | None] = mapped_column(String(100))
    primary_service_line: Mapped[str | None] = mapped_column(String(100))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    onboarded_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="client")

class Invoice(Base):
    __tablename__ = "invoices"
    invoice_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.client_id"), index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    service_line_account: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18,2))
    gst_rate_percent: Mapped[Decimal] = mapped_column(Numeric(7,4))
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(18,2))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(18,2))
    status: Mapped[str] = mapped_column(String(24), index=True)
    last_payment_date: Mapped[date | None] = mapped_column(Date)
    po_number: Mapped[str | None] = mapped_column(String(60))
    carried_in_from_prior_period: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.entry_id"), nullable=True)
    client: Mapped[Client] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", order_by="InvoiceItem.line_no")
    payments: Mapped[list["InvoicePayment"]] = relationship(back_populates="invoice", order_by="InvoicePayment.payment_date")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    invoice_item_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.invoice_id", ondelete="RESTRICT"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12,3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18,2))
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    revenue_account: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    invoice: Mapped[Invoice] = relationship(back_populates="items")
    __table_args__ = (UniqueConstraint("invoice_id", "line_no", name="uq_invoice_item_line"),)

class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    payment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.invoice_id", ondelete="RESTRICT"), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2))
    payment_mode: Mapped[str] = mapped_column(String(40))
    reference_no: Mapped[str | None] = mapped_column(String(100))
    received_by: Mapped[str | None] = mapped_column(String(30))
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.entry_id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    invoice: Mapped[Invoice] = relationship(back_populates="payments")

class Vendor(Base):
    __tablename__ = "vendors"
    vendor_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(200), index=True)
    primary_expense_account: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    payment_terms_days: Mapped[int] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gst_registration: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    bills: Mapped[list["ExpenseBill"]] = relationship(back_populates="vendor")

class ExpenseBill(Base):
    __tablename__ = "expense_bills"
    expense_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    category_account: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), index=True)
    bill_reference: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(500))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.department_id"), nullable=True)
    amount_excl_gst: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    gst_rate_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    source_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    submitted_by: Mapped[str] = mapped_column(String(40))
    approved_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.entry_id"), nullable=True)
    payment_ledger_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.entry_id"), nullable=True)
    legacy_sod_violation: Mapped[bool] = mapped_column(default=False)
    vendor: Mapped[Vendor] = relationship(back_populates="bills")
    approval_history: Mapped[list["ExpenseApprovalHistory"]] = relationship(back_populates="bill", order_by="ExpenseApprovalHistory.history_id")
    payments: Mapped[list["ExpensePayment"]] = relationship(back_populates="bill")
    __table_args__ = (
        CheckConstraint("amount_excl_gst >= 0 AND gst_amount >= 0 AND total_amount >= 0", name="ck_expense_bill_nonnegative"),
        CheckConstraint("total_amount = amount_excl_gst + gst_amount", name="ck_expense_bill_total"),
    )

class ExpenseApprovalHistory(Base):
    __tablename__ = "expense_approval_history"
    history_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    expense_id: Mapped[str] = mapped_column(ForeignKey("expense_bills.expense_id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    legacy_import: Mapped[bool] = mapped_column(default=False)
    bill: Mapped[ExpenseBill] = relationship(back_populates="approval_history")

class ExpensePayment(Base):
    __tablename__ = "expense_payments"
    payment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    expense_id: Mapped[str] = mapped_column(ForeignKey("expense_bills.expense_id", ondelete="RESTRICT"), unique=True, index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash_account_code: Mapped[str] = mapped_column(ForeignKey("chart_of_accounts.account_code"))
    payment_mode: Mapped[str] = mapped_column(String(40))
    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ledger_entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.entry_id"))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    bill: Mapped[ExpenseBill] = relationship(back_populates="payments")
