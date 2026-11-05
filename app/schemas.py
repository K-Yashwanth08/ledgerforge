from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

class UserCreate(BaseModel):
    employee_id: str | None = Field(default=None, max_length=20)
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    role: str

class UserPatch(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=255)
    role: str | None = None
    is_active: bool | None = None

class UserPasswordChange(BaseModel):
    password: str = Field(min_length=12, max_length=128)

class UserOut(BaseModel):
    user_id: str
    employee_id: str | None
    username: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    department_id: str
    department_name: str
    cost_center: str
    description: str | None = None

class RoleOut(BaseModel):
    role_id: str
    department_id: str
    role_title: str
    level: int
    grade: str
    model_config = ConfigDict(from_attributes=True)

class EmployeeCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=201)
    work_email: str = Field(min_length=3, max_length=255)
    hire_date: date
    employment_status: str = "Active"
    employment_type: str = "Permanent"
    department_id: str
    role_id: str
    manager_id: str | None = None
    work_location: str | None = None
    work_mode: str | None = None

class EmployeePatch(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=201)
    work_email: str | None = Field(default=None, min_length=3, max_length=255)
    employment_status: str | None = None
    employment_type: str | None = None
    department_id: str | None = None
    role_id: str | None = None
    manager_id: str | None = None
    work_location: str | None = None
    work_mode: str | None = None

class EmployeeOut(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    full_name: str
    work_email: str
    hire_date: date
    exit_date: date | None
    employment_status: str
    employment_type: str
    department_id: str
    department_name: str | None = None
    role_id: str
    role_title: str | None = None
    manager_id: str | None
    work_location: str | None
    work_mode: str | None
    model_config = ConfigDict(from_attributes=True)

class SalaryComponentAmountIn(BaseModel):
    component_id: str
    monthly_amount: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)

class SalaryRevisionCreate(BaseModel):
    effective_from: date
    revision_reason: str = Field(min_length=1, max_length=200)
    components: list[SalaryComponentAmountIn] = Field(min_length=1)
    role_id_after: str | None = None
    approved_by: str | None = Field(default=None, max_length=30)

class SalaryComponentOut(BaseModel):
    component_id: str
    component_name: str
    component_type: str
    taxable: bool
    is_fixed: bool
    monthly_amount: Decimal

class SalaryStructureOut(BaseModel):
    employee_id: str
    effective_date: date
    annual_fixed: Decimal
    components: list[SalaryComponentOut]

class SalaryRevisionOut(BaseModel):
    revision_id: str
    employee_id: str
    effective_from: date
    revision_reason: str
    previous_annual_fixed: Decimal | None
    new_annual_fixed: Decimal
    pct_change: Decimal | None
    role_id_after: str
    approved_by: str | None
    created_at: date
    model_config = ConfigDict(from_attributes=True)

class AttendanceOut(BaseModel):
    attendance_id: str
    employee_id: str
    attendance_date: date
    weekday: str
    status: str
    leave_type_code: str | None
    check_in: str | None
    check_out: str | None
    hours_worked: Decimal | None
    overtime_hours: Decimal | None
    late_flag: str | None
    data_quality_flag: str | None
    department_id: str | None
    model_config = ConfigDict(from_attributes=True)

class AttendanceSummaryOut(BaseModel):
    employee_id: str
    month: str
    days_present: int
    work_from_home_days: int
    absent_days: Decimal
    paid_leave_days: int
    unpaid_leave_days: int
    late_occurrences: int
    overtime_hours: Decimal
    missing_checkout_records: int

class LeaveTypeOut(BaseModel):
    leave_type_code: str
    leave_type_name: str
    pay_type: str
    annual_quota_days: Decimal
    prorated_for_joiners: bool
    carry_forward_allowed: bool
    max_carry_forward_days: Decimal
    policy_note: str | None
    model_config = ConfigDict(from_attributes=True)

class LeaveBalanceOut(BaseModel):
    employee_id: str
    leave_type_code: str
    financial_year: str
    as_of_date: date
    entitlement_days: Decimal
    used_days: Decimal
    balance_days: Decimal
    model_config = ConfigDict(from_attributes=True)

class LeaveRequestCreate(BaseModel):
    employee_id: str
    leave_type_code: str
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=500)
    is_half_day: bool = False

class LeaveRequestOut(BaseModel):
    leave_request_id: str
    employee_id: str
    leave_type_code: str
    start_date: date
    end_date: date
    days: Decimal
    reason: str
    status: str
    applied_on: date
    approver_id: str | None
    decided_on: date | None
    is_half_day: bool
    model_config = ConfigDict(from_attributes=True)

class PayrollItemOut(BaseModel):
    payroll_item_id: str
    run_id: str
    employee_id: str
    period_start: date
    period_end: date
    calendar_days: int
    days_employed: int
    lop_days: Decimal
    payable_days: Decimal
    monthly_fixed_gross: Decimal
    basic: Decimal
    hra: Decimal
    conveyance: Decimal
    medical: Decimal
    special_allowance: Decimal
    earned_fixed_pay: Decimal
    overtime_hours_paid: Decimal
    overtime_pay: Decimal
    variable_pay: Decimal
    variable_pay_type: str | None
    gross_pay: Decimal
    pf_employee: Decimal
    esi_employee: Decimal
    professional_tax: Decimal
    tds: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    pf_employer: Decimal
    esi_employer: Decimal
    employer_cost: Decimal
    calculation_note: str | None
    model_config = ConfigDict(from_attributes=True)

class PayrollRunOut(BaseModel):
    run_id: str
    period_start: date
    period_end: date
    pay_date: date | None
    employees_paid: int
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
    total_employer_contributions: Decimal
    total_employer_cost: Decimal
    status: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    journal_entry_id: str | None = None
    payment_journal_entry_id: str | None = None
    reversal_entry_id: str | None = None
    payment_reversal_entry_id: str | None = None
    calculation_version: str
    warnings: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PayslipRunOut(BaseModel):
    run_id: str
    period_start: date
    period_end: date
    pay_date: date | None
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal

class PayrollRunCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    pay_date: date

class PayrollRunDraftCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    pay_date: date
    idempotency_key: str = Field(min_length=8, max_length=100)

class PayrollPaymentCreate(BaseModel):
    payment_date: date
    bank_account_code: str = Field(min_length=1, max_length=20)
    payment_mode: str = Field(min_length=1, max_length=40)
    reference_no: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)

class JournalLineCreate(BaseModel):
    account_code: str
    debit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    cost_center_department_id: str | None = None
    line_description: str = Field(default="", max_length=500)

class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=1, max_length=500)
    source_type: str = Field(default="MANUAL", min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=40)
    lines: list[JournalLineCreate] = Field(min_length=2, max_length=200)

class JournalLineOut(BaseModel):
    line_id: str
    entry_id: str
    line_no: int
    account_code: str
    debit: Decimal
    credit: Decimal
    cost_center_department_id: str | None
    line_description: str
    model_config = ConfigDict(from_attributes=True)

class JournalEntryOut(BaseModel):
    entry_id: str
    entry_date: date
    posting_period: str
    financial_year: str
    description: str
    source_type: str
    source_id: str | None
    status: str
    total_debit: Decimal
    total_credit: Decimal
    reversal_of_source_id: str | None
    lines: list[JournalLineOut] = Field(default_factory=list)

class AccountOut(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    parent_code: str | None
    is_group: bool
    statement: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class AccountBalanceOut(BaseModel):
    account_code: str
    account_name: str
    as_of: date
    normal_balance: str
    debits: Decimal
    credits: Decimal
    balance: Decimal

class ReversalCreate(BaseModel):
    entry_date: date
    reason: str = Field(min_length=1, max_length=500)

class ClientCreate(BaseModel):
    client_id: str = Field(min_length=1,max_length=20)
    client_name: str = Field(min_length=1,max_length=200)
    country: str = Field(min_length=1,max_length=80)
    payment_terms_days: int = Field(ge=0,le=365)
    industry: str | None = None
    city: str | None = None
    state_or_region: str | None = None
    client_type: str | None = None
    gst_registration: str | None = None
    payment_behaviour: str | None = None
    primary_service_line: str | None = None
    contact_email: str | None = None
    onboarded_on: date | None = None
    is_active: bool = True

class ClientOut(ClientCreate):
    model_config = ConfigDict(from_attributes=True)

class ClientPatch(BaseModel):
    client_name: str | None = Field(default=None,min_length=1,max_length=200)
    city: str | None = None
    state_or_region: str | None = None
    country: str | None = None
    payment_terms_days: int | None = Field(default=None,ge=0,le=365)
    contact_email: str | None = None
    is_active: bool | None = None

class InvoiceItemCreate(BaseModel):
    description: str = Field(min_length=1,max_length=500)
    quantity: Decimal = Field(gt=0,max_digits=12,decimal_places=3)
    unit_price: Decimal = Field(ge=0,max_digits=18,decimal_places=2)
    revenue_account: str

class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1,max_length=40)
    client_id: str
    invoice_date: date
    due_date: date
    currency: str = Field(default="INR",min_length=3,max_length=3)
    gst_rate_percent: Decimal = Field(ge=0,le=100,max_digits=7,decimal_places=4)
    po_number: str | None = Field(default=None,max_length=60)
    items: list[InvoiceItemCreate] = Field(min_length=1,max_length=100)

class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    due_date: date | None = None
    gst_rate_percent: Decimal | None = Field(default=None,ge=0,le=100,max_digits=7,decimal_places=4)
    po_number: str | None = Field(default=None,max_length=60)
    items: list[InvoiceItemCreate] | None = Field(default=None,min_length=1,max_length=100)

class InvoiceItemOut(BaseModel):
    invoice_item_id: str
    invoice_id: str
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    revenue_account: str
    model_config = ConfigDict(from_attributes=True)
    model_config = ConfigDict(from_attributes=True)

class InvoicePaymentOut(BaseModel):
    payment_id: str
    invoice_id: str
    payment_date: date
    amount: Decimal
    payment_mode: str
    reference_no: str | None
    received_by: str | None
    ledger_entry_id: str | None
    model_config = ConfigDict(from_attributes=True)

class InvoiceOut(BaseModel):
    invoice_id: str
    invoice_number: str
    client_id: str
    client_name: str | None = None
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    gst_rate_percent: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    status: str
    po_number: str | None
    ledger_entry_id: str | None
    items: list[InvoiceItemOut] = Field(default_factory=list)
    payments: list[InvoicePaymentOut] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PaymentCreate(BaseModel):
    payment_date: date
    amount: Decimal = Field(gt=0,max_digits=18,decimal_places=2)
    payment_mode: str = Field(min_length=1,max_length=40)
    reference_no: str | None = Field(default=None,max_length=100)
    idempotency_key: str = Field(min_length=8,max_length=100)

class InvoiceCancel(BaseModel):
    reason: str = Field(min_length=1,max_length=500)

class ReceivableOut(BaseModel):
    client_id: str
    client_name: str
    outstanding_balance: Decimal

class VendorCreate(BaseModel):
    vendor_id: str = Field(min_length=1, max_length=30)
    vendor_name: str = Field(min_length=1, max_length=200)
    primary_expense_account: str = Field(min_length=1, max_length=20)
    payment_terms_days: int = Field(ge=0, le=3650)
    city: str | None = Field(default=None, max_length=100)
    gst_registration: str | None = Field(default=None, max_length=40)
    is_active: bool = True

class VendorPatch(BaseModel):
    vendor_name: str | None = Field(default=None, min_length=1, max_length=200)
    primary_expense_account: str | None = Field(default=None, min_length=1, max_length=20)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    city: str | None = Field(default=None, max_length=100)
    gst_registration: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None

class VendorOut(BaseModel):
    vendor_id: str
    vendor_name: str
    primary_expense_account: str
    payment_terms_days: int
    city: str | None
    gst_registration: str | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class ExpenseBillCreate(BaseModel):
    vendor_id: str = Field(min_length=1, max_length=30)
    expense_date: date
    due_date: date
    bill_reference: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    category_account: str = Field(min_length=1, max_length=20)
    department_id: str | None = Field(default=None, max_length=10)
    amount_excl_gst: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    gst_rate_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)

class ExpenseDuplicateCheck(BaseModel):
    vendor_id: str
    bill_reference: str
    expense_date: date
    total_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

class ExpensePaymentCreate(BaseModel):
    payment_date: date
    payment_mode: str = Field(min_length=1, max_length=40)
    cash_account_code: str = Field(min_length=1, max_length=20)
    reference_no: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)

class ExpenseBillOut(BaseModel):
    expense_id: str
    expense_date: date
    category_account: str
    vendor_id: str
    bill_reference: str
    description: str
    department_id: str | None
    amount_excl_gst: Decimal
    gst_rate_percent: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    due_date: date
    paid_date: date | None
    status: str
    source_status: str | None
    payment_mode: str | None
    submitted_by: str
    approved_by: str | None
    approved_at: datetime | None
    ledger_entry_id: str | None
    payment_ledger_entry_id: str | None
    legacy_sod_violation: bool
    approval_history: list[dict] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
