"""Idempotently load supplied payroll/tax reference snapshots and parameters."""
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import PayrollItem, PayrollRun, StatutoryRate, TaxParameter, TaxSlab
from scripts.load_phase2_task6 import BATCH_SIZE, conflict_safe_insert

DATA = Path(settings.data_dir)

def read(filename):
    path = DATA / filename
    if not path.is_file(): raise FileNotFoundError(f"Required payroll source CSV is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f: yield from csv.DictReader(f)

def chunks(filename, converter):
    batch=[]
    for row in read(filename):
        batch.append(converter(row))
        if len(batch) >= BATCH_SIZE:
            yield batch; batch=[]
    if batch: yield batch

def dec(v): return Decimal(v) if v not in (None, "") else Decimal("0")
def dt(v): return datetime.fromisoformat(v) if v else None
def day(v): return date.fromisoformat(v) if v else None

def main():
    with SessionLocal.begin() as db:
        rate_count=0
        for batch in chunks("statutory_rates.csv", lambda r: {**r,"effective_from":date.fromisoformat(r["effective_from"]),"value":dec(r["value"])}): rate_count += conflict_safe_insert(db,StatutoryRate,batch)
        tax_count=0
        for batch in chunks("tax_parameters.csv",lambda r:{**r,"value":dec(r["value"]),
            "financial_year":"FY2025-26","regime":"NEW","effective_from":date(1900,1,1)}): tax_count += conflict_safe_insert(db,TaxParameter,batch)
        slab_count=0
        for batch in chunks("tax_slabs.csv",lambda r:{**r,"income_from":dec(r["income_from"]),"income_to":dec(r["income_to"]) if r["income_to"] else None,"rate_percent":dec(r["rate_percent"]),"effective_from":date.fromisoformat(r["effective_from"])}): slab_count += conflict_safe_insert(db,TaxSlab,batch)
        run_count=0
        for batch in chunks("payroll_runs.csv",lambda r:{**r,
            **{k:day(r[k]) for k in ("period_start","period_end","pay_date")},
            **{k:int(r[k]) for k in ("employees_paid",)},
            **{k:dec(r[k]) for k in ("total_gross","total_deductions","total_net","total_employer_contributions","total_employer_cost")},
            "created_at":dt(r["created_at"]),"approved_at":dt(r["approved_at"]),"run_by":r["run_by"] or None,
            "approved_by":r["approved_by"] or None,"idempotency_key":r["idempotency_key"] or None,
            "journal_entry_id":r["journal_entry_id"] or None}): run_count += conflict_safe_insert(db,PayrollRun,batch)
        item_count=0
        decimal_fields=("lop_days","payable_days","monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance","earned_fixed_pay","overtime_hours_paid","overtime_pay","variable_pay","gross_pay","pf_employee","esi_employee","professional_tax","tds","other_deductions","total_deductions","net_pay","pf_employer","esi_employer","employer_cost")
        int_fields=("calendar_days","days_employed")
        for batch in chunks("payroll_items.csv",lambda r:{**r,
            **{k:date.fromisoformat(r[k]) for k in ("period_start","period_end")},
            **{k:int(r[k]) for k in int_fields},**{k:dec(r[k]) for k in decimal_fields},
            "variable_pay_type":r["variable_pay_type"] or None,"calculation_note":r["calculation_note"] or None}): item_count += conflict_safe_insert(db,PayrollItem,batch)
    print(f"Task 7 input load complete: statutory rates={rate_count}, tax parameters={tax_count}, tax slabs={slab_count}, payroll runs={run_count}, payroll items={item_count}; existing IDs preserved.")

if __name__ == "__main__": main()
