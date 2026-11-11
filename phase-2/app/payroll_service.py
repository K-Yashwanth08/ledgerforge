"""Deterministic payroll calculation using effective-dated project inputs."""
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from .models import (AttendanceRecord, Employee, EmployeeAssignment, PayrollItem, PayrollRun, Role,
                     SalaryComponent, SalaryStructure, StatutoryRate, TaxParameter, TaxSlab)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
VERSION = "ledgerforge-payroll-2"

def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))

def round_money(value) -> Decimal:
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)

def financial_year(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"FY{y}-{(y + 1) % 100:02d}"

def _rates(db: Session, d: date) -> dict[str, Decimal]:
    rows = db.query(StatutoryRate).filter(StatutoryRate.effective_from <= d).order_by(StatutoryRate.effective_from).all()
    values = {}
    for row in rows: values[row.parameter] = D(row.value)
    return values

def _tax_params(db: Session) -> dict[str, Decimal]:
    return {r.parameter: D(r.value) for r in db.query(TaxParameter).all()}

def _effective_tax_slabs(db: Session, fy: str, as_of: date) -> list[TaxSlab]:
    effective_from = db.query(func.max(TaxSlab.effective_from)).filter(
        TaxSlab.financial_year == fy, TaxSlab.regime == "NEW", TaxSlab.effective_from <= as_of
    ).scalar()
    if effective_from is None:
        return []
    return db.query(TaxSlab).filter_by(financial_year=fy, regime="NEW", effective_from=effective_from).order_by(
        TaxSlab.income_from).all()

def _annual_tax(db: Session, annual_salary: Decimal, fy: str, params: dict[str, Decimal], as_of: date) -> Decimal:
    standard = params.get("standard_deduction")
    rebate_limit = params.get("rebate_threshold_taxable")
    cess = params.get("health_education_cess_percent")
    if standard is None or rebate_limit is None or cess is None:
        raise HTTPException(503, "Tax parameters are incomplete")
    taxable = max(ZERO, annual_salary - standard)
    slabs = _effective_tax_slabs(db, fy, as_of)
    if not slabs:
        raise HTTPException(503, f"No configured tax slabs for {fy}")
    tax = ZERO
    for slab in slabs:
        low = D(slab.income_from)
        high = D(slab.income_to) if slab.income_to is not None else taxable
        portion = max(ZERO, min(taxable, high) - low)
        tax += portion * D(slab.rate_percent) / Decimal("100")
    if taxable <= rebate_limit:
        tax = ZERO
    else:
        tax = min(tax, taxable - rebate_limit)  # configured marginal-relief cap
    return round_money(tax * (Decimal("1") + cess / Decimal("100")))

def calculate_employee_month(db: Session, employee_id: str, month: str,
                             variable_pay: Decimal = ZERO, variable_pay_type: str | None = None,
                             other_deductions: Decimal = ZERO, *, capture_inputs: bool = False) -> dict:
    try:
        year, mon = map(int, month.split("-"))
        start = date(year, mon, 1)
        end = date(year, mon, monthrange(year, mon)[1])
    except (ValueError, TypeError):
        raise HTTPException(422, "month must use YYYY-MM format")
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(404, "Employee not found")
    active_start = max(start, employee.hire_date)
    active_end = min(end, employee.exit_date or end)
    days_employed = max(0, (active_end - active_start).days + 1)
    calendar_days = (end - start).days + 1
    if days_employed == 0:
        raise HTTPException(422, "Employee was not employed during this month")
    rows = db.query(SalaryStructure, SalaryComponent).join(SalaryComponent,
        SalaryComponent.component_id == SalaryStructure.component_id).filter(
        SalaryStructure.employee_id == employee_id, SalaryStructure.is_active.is_(True),
        SalaryStructure.effective_from <= active_start,
        (SalaryStructure.effective_to.is_(None) | (SalaryStructure.effective_to >= active_start))).all()
    fixed = {c.component_id: D(s.monthly_amount) for s, c in rows
             if c.component_type == "EARNING" and c.is_fixed}
    if not fixed:
        raise HTTPException(404, f"No applicable fixed salary structure for {employee_id} in {month}")
    monthly_fixed = sum(fixed.values(), ZERO)
    att = db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.attendance_date.between(active_start, active_end)).all()
    lop = sum((Decimal("0.5") if r.status == "HALF_DAY_UNPAID" else Decimal("1"))
              for r in att if r.status in {"ABSENT_LOP", "HALF_DAY_UNPAID", "UNPAID_LEAVE"})
    lop = min(Decimal(days_employed), lop)
    payable = max(ZERO, Decimal(days_employed) - lop)
    components = {code: round_money(value * payable / Decimal(calendar_days)) for code, value in fixed.items()}
    # Round each salary component independently, then total those booked amounts.
    # The supplied payroll reference uses this order: rounding aggregate fixed pay
    # first can differ from the sum of rounded component lines by one paisa.
    earned = sum(components.values(), ZERO)
    basic = components.get("BASIC", ZERO); hra = components.get("HRA", ZERO)
    conveyance = components.get("CONV", ZERO); medical = components.get("MED", ZERO)
    special = earned - basic - hra - conveyance - medical
    if special < 0:
        raise HTTPException(422, "Configured salary components do not match the supported payroll breakdown")
    rate_rows = db.query(StatutoryRate).filter(StatutoryRate.effective_from <= start).order_by(
        StatutoryRate.effective_from, StatutoryRate.parameter).all()
    selected_rate_rows = {}
    for rate_row in rate_rows:
        selected_rate_rows[rate_row.parameter] = rate_row
    rates = {name: D(row.value) for name, row in selected_rate_rows.items()}
    required = {"PF_EMPLOYEE_RATE", "PF_EMPLOYER_RATE", "PF_WAGE_CEILING", "ESI_EMPLOYEE_RATE",
                "ESI_EMPLOYER_RATE", "ESI_WAGE_LIMIT", "PT_MONTHLY", "PT_GROSS_THRESHOLD",
                "OT_MULTIPLIER", "OT_MONTHLY_CAP_HOURS", "WORKING_HOURS_PER_MONTH"}
    missing = required - rates.keys()
    if missing: raise HTTPException(503, "Missing configured statutory rates: " + ", ".join(sorted(missing)))
    # Eligibility follows the role assigned on each attendance date. Attendance
    # hours remain source-provided; assignment effective_to is inclusive.
    attendance_ot = [r for r in att if D(r.overtime_hours) > ZERO]
    assignment_by_date: dict[date, EmployeeAssignment] = {}
    roles_by_id: dict[str, Role | None] = {}
    for attendance_date in {r.attendance_date for r in attendance_ot}:
        assignments = db.query(EmployeeAssignment).filter(
            EmployeeAssignment.employee_id == employee_id,
            EmployeeAssignment.effective_from <= attendance_date,
            (EmployeeAssignment.effective_to.is_(None) |
             (EmployeeAssignment.effective_to >= attendance_date)),
        ).all()
        if not assignments:
            raise HTTPException(422, f"No effective role assignment for overtime on {attendance_date}")
        if len(assignments) > 1:
            raise HTTPException(422, f"Overlapping role assignments for overtime on {attendance_date}")
        assignment_by_date[attendance_date] = assignments[0]
    eligible_ot_hours = ZERO
    for row in attendance_ot:
        assignment = assignment_by_date[row.attendance_date]
        if assignment.role_id not in roles_by_id:
            roles_by_id[assignment.role_id] = db.get(Role, assignment.role_id)
        role = roles_by_id[assignment.role_id]
        if role is not None and (role.overtime_eligible or "N").upper() == "Y":
            eligible_ot_hours += D(row.overtime_hours)
    ot_hours = min(eligible_ot_hours, rates["OT_MONTHLY_CAP_HOURS"])
    # Multiply before dividing so repeating Decimal quotients do not land just
    # below a half-cent and round down when the exact result is a half-cent.
    overtime = round_money(monthly_fixed * rates["OT_MULTIPLIER"] * ot_hours / rates["WORKING_HOURS_PER_MONTH"])
    variable_pay = round_money(variable_pay)
    gross = earned + overtime + variable_pay
    basic_for_pf = min(basic, rates["PF_WAGE_CEILING"])
    pf_ee = round_money(basic_for_pf * rates["PF_EMPLOYEE_RATE"] / 100) if employee.pf_applicable == "Y" else ZERO
    pf_er = round_money(basic_for_pf * rates["PF_EMPLOYER_RATE"] / 100) if employee.pf_applicable == "Y" else ZERO
    eligible_esi = employee.esi_applicable == "Y" and monthly_fixed <= rates["ESI_WAGE_LIMIT"]
    esi_ee = round_money(gross * rates["ESI_EMPLOYEE_RATE"] / 100) if eligible_esi else ZERO
    esi_er = round_money(gross * rates["ESI_EMPLOYER_RATE"] / 100) if eligible_esi else ZERO
    pt = rates["PT_MONTHLY"] if gross >= rates["PT_GROSS_THRESHOLD"] else ZERO
    tax_params = _tax_params(db)
    annual_salary = monthly_fixed * Decimal("12")
    annual_tax = _annual_tax(db, annual_salary, financial_year(start), tax_params, start)
    tds = round_money(annual_tax / Decimal("12"))
    other = round_money(other_deductions)
    deductions = pf_ee + esi_ee + pt + tds + other
    net = gross - deductions
    warnings = ["Tax slabs and statutory rates are explicitly marked SAMPLE; this is not a statutory payroll result.",
                "No variable-pay source dataset is supplied; variable pay defaults to zero unless explicitly provided.",
                "No employee-loan/advance dataset is supplied; other deductions default to zero unless explicitly provided.",
                "Tax regime and individual tax declarations are not supplied; the configured NEW regime is used."]
    result = {"employee_id": employee_id, "month": month, "period_start": start, "period_end": end,
        "calendar_days": calendar_days, "days_employed": days_employed, "lop_days": lop, "payable_days": payable,
        "monthly_fixed_gross": monthly_fixed, "basic": basic, "hra": hra, "conveyance": conveyance,
        "medical": medical, "special_allowance": special, "earned_fixed_pay": earned,
        "overtime_hours_paid": ot_hours, "overtime_pay": overtime, "variable_pay": variable_pay,
        "variable_pay_type": variable_pay_type, "gross_pay": gross, "pf_employee": pf_ee,
        "esi_employee": esi_ee, "professional_tax": pt, "tds": tds, "other_deductions": other,
        "total_deductions": deductions, "net_pay": net, "pf_employer": pf_er, "esi_employer": esi_er,
        "employer_cost": gross + pf_er + esi_er, "warnings": warnings,
        "calculation_note": "Calendar-day LOP; configured overtime policy; sample reference rates only."}
    if capture_inputs:
        tax_slabs = _effective_tax_slabs(db, financial_year(start), start)
        result["_input_snapshot"] = {
            "calculation_version": VERSION,
            "rounding": {"mode": "ROUND_HALF_UP", "currency_decimal_places": 2},
            "period": {"month": month, "start": start.isoformat(), "end": end.isoformat(),
                       "active_start": active_start.isoformat(), "active_end": active_end.isoformat()},
            "employee": {"employee_id": employee.employee_id, "hire_date": employee.hire_date.isoformat(),
                         "exit_date": employee.exit_date.isoformat() if employee.exit_date else None,
                         "pf_applicable": employee.pf_applicable, "esi_applicable": employee.esi_applicable},
            "salary_components": [{"structure_id": s.structure_id, "revision_id": s.revision_id,
                                   "component_id": c.component_id, "component_type": c.component_type,
                                   "is_fixed": c.is_fixed, "monthly_amount": format(D(s.monthly_amount), "f"),
                                   "effective_from": s.effective_from.isoformat(),
                                   "effective_to": s.effective_to.isoformat() if s.effective_to else None}
                                  for s, c in rows if c.component_type == "EARNING" and c.is_fixed],
            "attendance": [{"attendance_id": r.attendance_id, "date": r.attendance_date.isoformat(),
                            "status": r.status, "overtime_hours": format(D(r.overtime_hours), "f")}
                           for r in att],
            "overtime_assignments": [{"date": d.isoformat(), "assignment_id": assignment.assignment_id,
                                      "role_id": assignment.role_id,
                                      "role_overtime_eligible": bool((roles_by_id.get(assignment.role_id).overtime_eligible or "N").upper() == "Y")
                                      if roles_by_id.get(assignment.role_id) else False}
                                     for d, assignment in sorted(assignment_by_date.items())],
            "statutory_rates": {name: {"effective_from": row.effective_from.isoformat(),
                                       "value": format(D(row.value), "f"), "unit": row.unit, "note": row.note}
                                for name, row in selected_rate_rows.items()},
            "tax_parameters": {name: format(value, "f") for name, value in tax_params.items()},
            "tax_slabs": [{"slab_id": slab.slab_id, "regime": slab.regime,
                           "financial_year": slab.financial_year, "income_from": format(D(slab.income_from), "f"),
                           "income_to": format(D(slab.income_to), "f") if slab.income_to is not None else None,
                           "rate_percent": format(D(slab.rate_percent), "f"),
                           "effective_from": slab.effective_from.isoformat(), "note": slab.note}
                          for slab in tax_slabs],
            "manual_inputs": {"variable_pay": format(D(variable_pay), "f"),
                              "variable_pay_type": variable_pay_type,
                              "other_deductions": format(D(other_deductions), "f")},
            "policy": {"loss_of_pay": "calendar days; unpaid leave and absent statuses; half-day unpaid=0.5",
                       "overtime": "effective role eligibility; configured multiplier, monthly cap, and hours divisor",
                       "tax_regime": "NEW", "source_values_may_be_sample": any(
                           "sample" in str(row.note).casefold() for row in selected_rate_rows.values()) or
                           any("sample" in str(slab.note).casefold() for slab in tax_slabs) or
                           any("sample" in str(value).casefold() for value in
                               db.query(TaxParameter.note).all())},
        }
    return result

def run_payroll_month(db: Session, month: str, pay_date: date) -> tuple[PayrollRun, list[str]]:
    try:
        year, mon = map(int, month.split("-")); start = date(year, mon, 1); end = date(year, mon, monthrange(year, mon)[1])
    except (ValueError, TypeError):
        raise HTTPException(422, "month must use YYYY-MM format")
    key = f"{VERSION}:{month}"
    existing = db.query(PayrollRun).filter_by(idempotency_key=key).first()
    if existing:
        return existing, ["Existing immutable payroll calculation returned for this month."]
    employees = db.query(Employee).filter(Employee.hire_date <= end,
        (Employee.exit_date.is_(None) | (Employee.exit_date >= start))).order_by(Employee.employee_id).all()
    if not employees:
        raise HTTPException(422, "No employees were employed during this month")
    calculations = []
    for employee in employees:
        try: calculations.append(calculate_employee_month(db, employee.employee_id, month, capture_inputs=True))
        except HTTPException as exc:
            if exc.status_code == 404 and "salary structure" in str(exc.detail): continue
            raise
    if not calculations:
        raise HTTPException(422, "No employees have applicable salary structures for this month")
    version_tag = f"V{VERSION.rsplit('-', 1)[-1]}"
    run_id = f"LF-{month.replace('-', '')}-{version_tag}"
    totals = {k: sum((r[k] for r in calculations), ZERO) for k in
        ("gross_pay", "total_deductions", "net_pay", "employer_cost", "pf_employer", "esi_employer")}
    run = PayrollRun(run_id=run_id, period_start=start, period_end=end, pay_date=pay_date,
        employees_paid=len(calculations), total_gross=totals["gross_pay"], total_deductions=totals["total_deductions"],
        total_net=totals["net_pay"], total_employer_contributions=totals["pf_employer"]+totals["esi_employer"],
        total_employer_cost=totals["employer_cost"], status="CALCULATED", run_by=None, approved_by=None,
        created_at=None, approved_at=None, idempotency_key=key, journal_entry_id=None, calculation_version=VERSION)
    try:
        db.add(run); db.flush()
        db.add_all([PayrollItem(payroll_item_id=f"{run_id}:{r['employee_id']}", run_id=run_id,
            employee_id=r["employee_id"], period_start=start, period_end=end, department_id=db.get(Employee,r["employee_id"]).department_id,
            role_id=db.get(Employee,r["employee_id"]).role_id, calculation_note=r["calculation_note"],
            calculation_input_snapshot=json.dumps(r["_input_snapshot"], sort_keys=True, separators=(",", ":")),
            **{k:r[k] for k in ("calendar_days","days_employed","lop_days","payable_days","monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance","earned_fixed_pay","overtime_hours_paid","overtime_pay","variable_pay","variable_pay_type","gross_pay","pf_employee","esi_employee","professional_tax","tds","other_deductions","total_deductions","net_pay","pf_employer","esi_employer","employer_cost")}) for r in calculations])
        db.commit(); db.refresh(run)
    except Exception:
        db.rollback(); raise
    warnings = sorted({w for r in calculations for w in r["warnings"]})
    return run, warnings
