import csv
from datetime import date
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..financial_reports import balance_sheet, profit_and_loss, trial_balance
from ..models import PayrollItem, PayrollRun, StatutoryRate, TaxParameter, TaxSlab
from ..security import hr_actor

router = APIRouter(prefix="/reports", tags=["financial reports"])


@router.get("/statutory/monthly")
def statutory_monthly_report(start_date: date, end_date: date,
                             db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    if end_date < start_date:
        from fastapi import HTTPException
        raise HTTPException(422, "end_date must be on or after start_date")
    items = db.query(PayrollItem).filter(PayrollItem.period_start >= start_date,
        PayrollItem.period_start <= end_date).all()
    runs = {r.run_id: r for r in db.query(PayrollRun).filter(
        PayrollRun.period_start >= start_date, PayrollRun.period_start <= end_date,
        PayrollRun.status != "REVERSED").all()}
    policy_notes = [row.note for model in (StatutoryRate, TaxParameter, TaxSlab)
                    for row in db.query(model.note).filter(model.is_active.is_(True)).all()]
    policy_status = ("SAMPLE" if any("sample" in note.casefold() or "training" in note.casefold()
                                     for note in policy_notes)
                     else "UNVERIFIED" if policy_notes else "MISSING")
    grouped = {}
    for item in items:
        if item.run_id not in runs:
            continue
        month = item.period_start.strftime("%Y-%m")
        row = grouped.setdefault(month, {key: Decimal("0.00") for key in (
            "pf_employee", "pf_employer", "esi_employee", "esi_employer", "tds", "gross_pay",
            "total_deductions", "net_pay", "employer_cost")})
        for key in row:
            row[key] += getattr(item, key)
    months = []
    for month, totals in sorted(grouped.items()):
        month_runs = [r for r in runs.values() if r.period_start.strftime("%Y-%m") == month]
        expected = {key: sum((getattr(r, run_field) for r in month_runs), Decimal("0.00"))
            for key, run_field in (("gross_pay", "total_gross"), ("total_deductions", "total_deductions"),
                                   ("net_pay", "total_net"), ("employer_cost", "total_employer_cost"))}
        expected["employer_contributions"] = sum((r.total_employer_contributions for r in month_runs), Decimal("0.00"))
        actual_contributions = totals["pf_employer"] + totals["esi_employer"]
        checks = {key: {"payroll_items": totals[key], "payroll_runs": amount,
                        "difference": totals[key] - amount, "matches": totals[key] == amount}
                  for key, amount in expected.items() if key in totals}
        checks["employer_contributions"] = {"payroll_items": actual_contributions,
            "payroll_runs": expected["employer_contributions"],
            "difference": actual_contributions - expected["employer_contributions"],
            "matches": actual_contributions == expected["employer_contributions"]}
        months.append({"month": month, **totals, "employer_contributions": actual_contributions,
                       "policy_status": policy_status,
                       "reconciliation": checks,
                       "reconciled": all(check["matches"] for check in checks.values())})
    totals = {key: sum((row[key] for row in months), Decimal("0.00")) for key in
        ("pf_employee", "pf_employer", "esi_employee", "esi_employer", "tds", "gross_pay",
         "total_deductions", "net_pay", "employer_cost", "employer_contributions")}
    return {"start_date": start_date, "end_date": end_date, "months": months, "totals": totals,
        "reconciled": all(row["reconciled"] for row in months),
        "policy_status": policy_status, "official_compliance_claimed": False,
        "source": "Persisted payroll item results; configuration changes never recalculate prior runs."}


@router.get("/trial-balance")
def trial_balance_report(start_date: date | None = None, end_date: date | None = None,
                         db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    return trial_balance(db, start_date, end_date)


@router.get("/trial-balance.csv", include_in_schema=True)
def trial_balance_export(start_date: date | None = None, end_date: date | None = None,
                         db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    report = trial_balance(db, start_date, end_date)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["account_code", "account_name", "debit", "credit", "opening_debit", "opening_credit",
                     "period_debit", "period_credit", "closing_debit", "closing_credit"])
    for row in report["rows"]:
        if row["is_group"]:
            continue
        writer.writerow([row["account_code"], row["account_name"], row["period_debit"], row["period_credit"],
                         row["opening_debit"], row["opening_credit"], row["period_debit"], row["period_credit"],
                         row["closing_debit"], row["closing_credit"]])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ledgerforge-trial-balance.csv"'})


@router.get("/profit-and-loss")
def profit_and_loss_report(start_date: date | None = None, end_date: date | None = None,
                           db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    return profit_and_loss(db, start_date, end_date)


@router.get("/balance-sheet")
def balance_sheet_report(start_date: date | None = None, end_date: date | None = None,
                         db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    return balance_sheet(db, start_date, end_date)
