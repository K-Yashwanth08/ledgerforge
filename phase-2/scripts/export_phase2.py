"""Export current database tables for the bundled reconciliation checker.

The target must be a new or empty directory. Export files are financial data
and are excluded from Git by the root ignore rules.
"""
import argparse
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from app.database import SessionLocal
from app.models import (ChartOfAccount,Employee,Invoice,JournalEntry,JournalLine,PayrollItem,PayrollRun)

def cell(value):
    if value is None:return ""
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,Decimal):return format(value,"f")
    return value

def write(path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader()
        for row in rows:writer.writerow({k:cell(v) for k,v in row.items()})

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",required=True,help="New/empty export folder; never point this at data/")
    target=Path(ap.parse_args().output).resolve()
    if target.name.lower()=="data":raise SystemExit("Refusing to export into the source data directory")
    if target.exists() and any(target.iterdir()):raise SystemExit(f"Refusing to overwrite non-empty export folder: {target}")
    target.mkdir(parents=True,exist_ok=True)
    with SessionLocal() as db:
        def records(model,fields):
            return [{f:getattr(r,f) for f in fields} for r in db.query(model).order_by(getattr(model,fields[0])).yield_per(1000)]
        specs=[
            ("chart_of_accounts.csv",ChartOfAccount,("account_code","account_name","account_type","normal_balance","parent_code","is_group","statement","is_active")),
            ("journal_entries.csv",JournalEntry,("entry_id","entry_date","posting_period","financial_year","description","source_type","source_id","status","total_debit","total_credit","reversal_of_source_id","created_by","created_at")),
            ("journal_lines.csv",JournalLine,("line_id","entry_id","line_no","account_code","debit","credit","cost_center_department_id","line_description")),
            ("payroll_runs.csv",PayrollRun,("run_id","period_start","period_end","pay_date","employees_paid","total_gross","total_deductions","total_net","total_employer_contributions","total_employer_cost","status","run_by","approved_by","created_at","approved_at","idempotency_key","journal_entry_id","calculation_version")),
            ("payroll_items.csv",PayrollItem,("payroll_item_id","run_id","employee_id","period_start","period_end","department_id","role_id","calendar_days","days_employed","lop_days","payable_days","monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance","earned_fixed_pay","overtime_hours_paid","overtime_pay","variable_pay","variable_pay_type","gross_pay","pf_employee","esi_employee","professional_tax","tds","other_deductions","total_deductions","net_pay","pf_employer","esi_employer","employer_cost","calculation_note")),
            ("invoices.csv",Invoice,("invoice_id","invoice_number","client_id","invoice_date","due_date","service_line_account","currency","subtotal","gst_rate_percent","gst_amount","total_amount","amount_paid","balance_due","status","last_payment_date","po_number","carried_in_from_prior_period","created_by","created_at","ledger_entry_id")),
            ("employees.csv",Employee,("employee_id","exit_date")),
        ]
        for filename,model,fields in specs:write(target/filename,fields,records(model,fields))
    print(f"Exported checker tables to {target}")
if __name__=="__main__":main()
