"""Run the configured payroll calculator for every supplied payroll scenario.

Benchmark rows supply only run/employee/period keys for calculation. Their
monetary values are read later solely to compare and classify differences.
"""
import argparse
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.payroll_service import calculate_employee_month

FIELDS=("run_id","employee_id","gross_pay","total_deductions","net_pay")
AMOUNTS=("gross_pay","total_deductions","net_pay")
DETAIL_FIELDS=("calendar_days","days_employed","lop_days","payable_days","monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance","earned_fixed_pay",
    "overtime_hours_paid","overtime_pay","variable_pay","gross_pay","pf_employee","esi_employee","professional_tax","tds",
    "other_deductions","total_deductions","net_pay","pf_employer","esi_employer","employer_cost")
CENT=Decimal("0.01")
def dec(v):return Decimal(v or "0")

def mismatch_cause(field):
    if field in {"calendar_days","days_employed"}:return "employment_period_or_calendar"
    if field in {"lop_days","payable_days"}:return "attendance_or_loss_of_pay_policy"
    if field=="variable_pay":return "variable_pay_source_missing_or_unapproved"
    if field in {"monthly_fixed_gross","basic","hra","conveyance","medical","special_allowance","earned_fixed_pay"}:
        return "salary_structure_or_lop_proration"
    if field in {"overtime_hours_paid","overtime_pay"}:return "overtime_input_or_policy"
    if field in {"pf_employee","pf_employer"}:return "pf_rate_wage_base_or_eligibility"
    if field in {"esi_employee","esi_employer"}:return "esi_rate_wage_base_or_eligibility"
    if field=="professional_tax":return "professional_tax_rule_or_state"
    if field=="tds":return "tax_regime_declarations_or_authoritative_rules"
    if field=="other_deductions":return "employee_loan_or_advance_schedule_missing"
    if field in {"gross_pay","total_deductions","net_pay","employer_cost"}:return "derived_from_component_mismatches"
    return "unresolved"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--reference",default=str(Path(settings.data_dir)/"payroll_items.csv"));ap.add_argument("--output-dir",default="outputs")
    args=ap.parse_args();out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    csv_path=out/"payroll-calculated.csv";mismatch_path=out/"payroll-mismatches.csv";summary_path=out/"payroll-mismatch-summary.json"
    if any(p.exists() for p in (csv_path,mismatch_path,summary_path)):
        raise SystemExit("Refusing to overwrite existing payroll validation artifacts")
    with open(args.reference,encoding="utf-8-sig",newline="") as f:reference=list(csv.DictReader(f))
    summary=Counter(); matches=0; full_row_matches=0; errors=[]
    with SessionLocal() as db, csv_path.open("w",encoding="utf-8",newline="") as cf, mismatch_path.open("w",encoding="utf-8",newline="") as mf:
        writer=csv.DictWriter(cf,fieldnames=FIELDS);writer.writeheader()
        mismatch=csv.DictWriter(mf,fieldnames=("run_id","employee_id","component","field","expected","calculated","difference","cause"));mismatch.writeheader()
        for row in reference:
            month=row["period_start"][:7]
            try:
                calc=calculate_employee_month(db,row["employee_id"],month)
            except Exception as exc:
                summary["calculation_error"]+=1;errors.append({"run_id":row["run_id"],"employee_id":row["employee_id"],"error":str(exc)})
                writer.writerow({"run_id":row["run_id"],"employee_id":row["employee_id"],"gross_pay":"","total_deductions":"","net_pay":""})
                mismatch.writerow({"run_id":row["run_id"],"employee_id":row["employee_id"],"component":"calculation","field":"calculation",
                    "expected":"","calculated":"","difference":"","cause":"no_applicable_salary_structure"})
                continue
            writer.writerow({"run_id":row["run_id"],"employee_id":row["employee_id"],
                **{k:format(calc[k],".2f") for k in AMOUNTS}})
            row_match=True; full_row_match=True
            for field in DETAIL_FIELDS:
                expected=dec(row[field]); actual=calc[field]; diff=expected-actual
                if abs(diff)>CENT:full_row_match=False
                if field in AMOUNTS and abs(diff)>CENT:row_match=False
                if abs(diff)>CENT:
                    cause=mismatch_cause(field)
                    summary[cause]+=1
                    mismatch.writerow({"run_id":row["run_id"],"employee_id":row["employee_id"],"component":field,"field":field,
                        "expected":format(expected,".2f"),"calculated":format(actual,".2f"),"difference":format(diff,".2f"),"cause":cause})
            if row_match:matches+=1
            if full_row_match:full_row_matches+=1
    report={"rows_expected":len(reference),"rows_written":len(reference),"rows_calculated":len(reference)-summary["calculation_error"],
        "calculation_errors":errors,"rows_matching_gross_deductions_net_within_one_paisa":matches,
        "overall_match_percent":round(matches*100/len(reference),2) if reference else 0,
        "rows_matching_all_compared_fields_within_one_paisa":full_row_matches,
        "all_compared_fields_match_percent":round(full_row_matches*100/len(reference),2) if reference else 0,
        "detail_field_mismatch_occurrences":sum(v for k,v in summary.items() if k!="calculation_error"),
        "mismatch_cause_occurrences":dict(summary),
        "mismatch_cause_note":"Cause labels are investigation categories inferred from mismatching fields; they do not establish an authoritative payroll rule.",
        "calculation_inputs":"salary structures, attendance, supplied parameter tables; reference monetary values used only for comparison"}
    summary_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Calculated {report['rows_calculated']}/{len(reference)} rows; gross/deductions/net matches within one paisa: {matches}; {report['overall_match_percent']:.2f}%")
    print(f"All compared fields within one paisa: {full_row_matches}; {report['all_compared_fields_match_percent']:.2f}%")
    print(f"Wrote {csv_path}, {mismatch_path}, {summary_path}")
if __name__=="__main__":main()
