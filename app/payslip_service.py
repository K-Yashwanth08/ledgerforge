from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .config import settings
from .models import Employee, PayrollItem, PayrollRun

CENT=Decimal("0.01")
def money(v): return (v if isinstance(v,Decimal) else Decimal(str(v or 0))).quantize(CENT,rounding=ROUND_HALF_UP)

def get_payslip_data(db: Session, employee_id: str, run_id: str) -> dict:
    run=db.get(PayrollRun,run_id)
    if not run: raise HTTPException(404,"Payroll run not found")
    item=db.query(PayrollItem).filter_by(run_id=run_id,employee_id=employee_id).first()
    if not item: raise HTTPException(404,"Payslip not found for this employee and payroll run")
    employee=db.get(Employee,employee_id)
    if not employee: raise HTTPException(404,"Employee not found")
    # PayrollItem components are already rounded and prorated by the calculator.
    # Applying the payable-days factor again understates component lines on LOP payslips.
    basic=money(item.basic); hra=money(item.hra); conveyance=money(item.conveyance)
    medical=money(item.medical); special=money(item.special_allowance)
    earnings=[]
    for label,amount in [("Basic salary",basic),("House rent allowance",hra),("Conveyance allowance",conveyance),
                         ("Medical allowance",medical),("Special allowance",special),("Overtime pay",item.overtime_pay),
                         ("Variable pay",item.variable_pay)]:
        if amount: earnings.append({"label":label,"amount":money(amount)})
    deductions=[]
    for label,amount in [("Provident fund",item.pf_employee),("Employee state insurance",item.esi_employee),
                         ("Professional tax",item.professional_tax),("Income tax withheld",item.tds),
                         ("Other deductions",item.other_deductions)]:
        if amount: deductions.append({"label":label,"amount":money(amount)})
    configured=settings.payslip_company_details_configured
    company_details={"legal_name":settings.company_legal_name,"address":settings.company_address,
                     "contact_email":settings.company_contact_email,"contact_phone":settings.company_contact_phone}
    missing=[]
    if not settings.company_legal_name: missing.append("registered legal name")
    if not settings.company_address: missing.append("legal address")
    if not (settings.company_contact_email or settings.company_contact_phone): missing.append("contact email or phone")
    details_note=(None if configured else "Payslip company details are incomplete; configure " + ", ".join(missing) + ".")
    return {"company_name":"LedgerForge","company_details":company_details,"company_details_configured":configured,
        "company_details_note":details_note,
        "currency":"INR","run_id":run.run_id,"period_start":run.period_start,"period_end":run.period_end,"pay_date":run.pay_date,
        "employee":{"employee_id":employee.employee_id,"full_name":employee.full_name,
            "department_name":employee.department.department_name if employee.department else None,
            "role_title":employee.role.role_title if employee.role else None},
        "earnings":earnings,"deductions":deductions,"gross_pay":money(item.gross_pay),
        "total_deductions":money(item.total_deductions),"net_pay":money(item.net_pay)}
