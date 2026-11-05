"""Attach supplied historical payroll payments to their existing ledger entries."""
import argparse
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import ChartOfAccount, JournalEntry, JournalLine, PayrollPayment, PayrollRun
from scripts.phase3_input_validation import validate_phase3_inputs


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _money(value):
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _bank_account(db, entry_id, amount):
    found = []
    for line in db.query(JournalLine).filter_by(entry_id=entry_id).all():
        account = db.get(ChartOfAccount, line.account_code)
        if (account and account.account_type == "ASSET" and account.is_active and not account.is_group
                and _money(line.credit) == amount and _money(line.debit) == 0
                and any(term in account.account_name.casefold() for term in ("bank", "cash"))):
            found.append(account)
    if len(found) != 1:
        raise ValueError(f"Salary payment {entry_id} does not identify exactly one cash/bank credit")
    return found[0].account_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=settings.data_dir)
    args = parser.parse_args()
    data = Path(args.data)
    validation = validate_phase3_inputs(data)
    if validation["errors"]:
        raise ValueError(f"Phase 3 validation failed: {validation['error_counts']}")
    runs = list(_rows(data / "payroll_runs.csv"))
    inserted = 0
    linked = 0
    with SessionLocal.begin() as db:
        for source in runs:
            run = db.get(PayrollRun, source["run_id"])
            if not run:
                raise ValueError(f"Existing payroll run {source['run_id']} is not loaded; import existing payroll source first")
            checks = (("period_start", date.fromisoformat(source["period_start"])),
                      ("period_end", date.fromisoformat(source["period_end"])),
                      ("pay_date", date.fromisoformat(source["pay_date"]) if source["pay_date"] else None),
                      ("total_gross", _money(source["total_gross"])),
                      ("total_deductions", _money(source["total_deductions"])),
                      ("total_net", _money(source["total_net"])),
                      ("total_employer_cost", _money(source["total_employer_cost"])),
                      ("journal_entry_id", source["journal_entry_id"] or None))
            for field, expected in checks:
                if getattr(run, field) != expected:
                    raise ValueError(f"Loaded payroll run {run.run_id} differs from the CSV in {field}; no values were overwritten")
            if run.status != source["status"]:
                raise ValueError(f"Loaded payroll run {run.run_id} has a different historical status; preserved unchanged")
            if source["status"] != "PAID":
                if db.query(PayrollPayment).filter_by(run_id=run.run_id).first():
                    raise ValueError(f"Pending payroll run {run.run_id} unexpectedly has a payroll payment")
                continue
            entry = db.query(JournalEntry).filter_by(source_type="SALARY_PAYMENT", source_id=run.run_id,
                                                     status="POSTED").one_or_none()
            if not entry or entry.entry_date != run.pay_date or entry.total_debit != entry.total_credit:
                raise ValueError(f"Paid payroll run {run.run_id} has no matching balanced salary payment journal")
            amount = _money(run.total_net)
            lines = db.query(JournalLine).filter_by(entry_id=entry.entry_id).all()
            account_lines = {}
            for line in lines:
                account_lines[line.account_code] = (_money(line.debit), _money(line.credit))
            payable = db.query(ChartOfAccount).filter_by(account_name="Salaries Payable",
                account_type="LIABILITY", is_group=False, is_active=True).one()
            bank_code = _bank_account(db, entry.entry_id, amount)
            expected_lines = {payable.account_code: (amount, Decimal("0.00")), bank_code: (Decimal("0.00"), amount)}
            if account_lines != expected_lines:
                raise ValueError(f"Salary payment journal {entry.entry_id} does not clear net salaries payable")
            if run.payment_journal_entry_id and run.payment_journal_entry_id != entry.entry_id:
                raise ValueError(f"Payroll run {run.run_id} has a different payment journal link; preserved unchanged")
            if not run.payment_journal_entry_id:
                run.payment_journal_entry_id = entry.entry_id
                linked += 1
            payment_id = f"IMP-PAY-{run.run_id}"
            payload = dict(payment_id=payment_id, run_id=run.run_id, payment_date=run.pay_date,
                amount=amount, bank_account_code=bank_code, payment_mode=None, reference_no=None,
                ledger_entry_id=entry.entry_id, idempotency_key=f"imported:payroll-payment:{run.run_id}",
                created_by=entry.created_by)
            existing = db.get(PayrollPayment, payment_id)
            if existing:
                if any(getattr(existing, key) != value for key, value in payload.items()):
                    raise ValueError(f"Payroll payment {run.run_id} differs from source; preserved unchanged")
            else:
                db.add(PayrollPayment(**payload)); inserted += 1
    print(f"Task 12 historic payment links complete: payment records inserted={inserted}, run links added={linked}.")
    print("Payroll totals, statuses, and posted journal entries were preserved.")


if __name__ == "__main__":
    main()
