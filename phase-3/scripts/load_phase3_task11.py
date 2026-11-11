"""Non-destructively import supplied vendors and expense bills."""
import argparse
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import (ChartOfAccount, ExpenseApprovalHistory, ExpenseBill, ExpensePayment,
                        JournalEntry, JournalLine, Vendor)
from scripts.phase3_input_validation import validate_phase3_inputs


def _rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _same(existing, payload):
    return all(getattr(existing, key) == value for key, value in payload.items())


def _snapshot_entry(db, entry_id, source_type, source_id, expected_date, debit, credit):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise ValueError(f"Required pre-existing ledger entry {entry_id} is not loaded")
    if (entry.source_type != source_type or entry.source_id != source_id or entry.status != "POSTED"
            or entry.entry_date != expected_date or Decimal(entry.total_debit) != debit
            or Decimal(entry.total_credit) != credit):
        raise ValueError(f"Database journal entry {entry_id} does not match the supplied immutable snapshot")
    return entry


def _payment_account(db, entry_id, amount):
    lines = db.query(JournalLine).filter_by(entry_id=entry_id).all()
    matches = []
    for line in lines:
        account = db.get(ChartOfAccount, line.account_code)
        if account and account.account_type == "ASSET" and not account.is_group and account.is_active:
            if Decimal(line.credit) == amount and Decimal(line.debit) == 0:
                matches.append(account)
    if len(matches) != 1 or not any(word in matches[0].account_name.casefold() for word in ("bank", "cash")):
        raise ValueError(f"Payment ledger entry {entry_id} does not identify exactly one cash/bank credit")
    return matches[0].account_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=settings.data_dir, help="Directory containing Phase 3 CSV files")
    args = parser.parse_args()
    data = Path(args.data)
    report = validate_phase3_inputs(data)
    if report["errors"]:
        raise ValueError(f"Phase 3 input validation failed: {report['error_counts']}")

    inserted = {"vendors": 0, "expense_bills": 0, "approval_history": 0, "payments": 0}
    with SessionLocal.begin() as db:
        vendor_rows = list(_rows(data / "vendors.csv"))
        expense_rows = list(_rows(data / "expenses.csv"))
        for row in vendor_rows:
            payload = {"vendor_id": row["vendor_id"], "vendor_name": row["vendor_name"],
                "primary_expense_account": row["primary_expense_account"].split(".")[0],
                "payment_terms_days": int(row["payment_terms_days"]), "city": row["city"] or None,
                "gst_registration": row["gst_registration"] or None, "is_active": row["is_active"].upper() == "Y"}
            existing = db.get(Vendor, payload["vendor_id"])
            if existing:
                if not _same(existing, payload): raise ValueError(f"Vendor {payload['vendor_id']} exists with different values; preserved without overwrite")
            else:
                db.add(Vendor(**payload)); inserted["vendors"] += 1
        db.flush()

        for row in expense_rows:
            expense_id = row["expense_id"]
            amount = Decimal(row["amount_excl_gst"]).quantize(Decimal("0.01"))
            gst = Decimal(row["gst_amount"]).quantize(Decimal("0.01"))
            total = Decimal(row["total_amount"]).quantize(Decimal("0.01"))
            bill_date = date.fromisoformat(row["expense_date"])
            paid_date = date.fromisoformat(row["paid_date"]) if row["paid_date"] else None
            bill_entry = _snapshot_entry(db, row["ledger_entry_id"], "EXPENSE", expense_id, bill_date, total, total)
            # Expense posting includes category cost, input GST, and AP; its header is balanced at total.
            status = "PAID" if row["status"].upper() == "PAID" else "APPROVED"
            payload = {"expense_id": expense_id, "expense_date": bill_date,
                "category_account": row["category_account"].split(".")[0], "vendor_id": row["vendor_id"],
                "bill_reference": row["bill_reference"], "description": row["description"],
                "department_id": row["department_id"] or None, "amount_excl_gst": amount,
                "gst_rate_percent": Decimal(row["gst_rate_percent"]), "gst_amount": gst,
                "total_amount": total, "due_date": date.fromisoformat(row["due_date"]),
                "paid_date": paid_date, "status": status, "source_status": row["status"].upper(),
                "payment_mode": row["payment_mode"] or None, "submitted_by": row["submitted_by"],
                "approved_by": row["approved_by"] or None, "approved_at": None,
                "ledger_entry_id": bill_entry.entry_id,
                "payment_ledger_entry_id": row["payment_ledger_entry_id"] or None,
                "legacy_sod_violation": bool(row["approved_by"] and row["approved_by"] == row["submitted_by"])}
            existing = db.get(ExpenseBill, expense_id)
            if existing:
                if not _same(existing, payload): raise ValueError(f"Expense {expense_id} exists with different values; preserved without overwrite")
                bill = existing
            else:
                bill = ExpenseBill(**payload); db.add(bill); db.flush(); inserted["expense_bills"] += 1

            for suffix, action, actor in (("S", "SUBMITTED", row["submitted_by"]),
                                          ("A", "APPROVED", row["approved_by"])):
                if not actor: continue
                history_id = f"IMP-{suffix}-{expense_id}"
                if not db.get(ExpenseApprovalHistory, history_id):
                    db.add(ExpenseApprovalHistory(history_id=history_id, expense_id=expense_id,
                        action=action, actor_id=actor, occurred_at=None, legacy_import=True))
                    inserted["approval_history"] += 1

            if row["payment_ledger_entry_id"]:
                payment_entry_id = row["payment_ledger_entry_id"]
                payment_entry = _snapshot_entry(db, payment_entry_id, "EXPENSE_PAYMENT", expense_id,
                    paid_date, total, total)
                payment_account = _payment_account(db, payment_entry_id, total)
                bill.payment_ledger_entry_id = payment_entry.entry_id
                payment_id = f"IMP-PAY-{expense_id}"
                payment_payload = {"payment_id": payment_id, "expense_id": expense_id,
                    "payment_date": paid_date, "amount": total, "cash_account_code": payment_account,
                    "payment_mode": row["payment_mode"], "reference_no": None,
                    "ledger_entry_id": payment_entry.entry_id,
                    "idempotency_key": f"imported:phase3:expense:{expense_id}"}
                payment = db.get(ExpensePayment, payment_id)
                if payment:
                    if not _same(payment, payment_payload): raise ValueError(f"Payment for {expense_id} differs from source; preserved without overwrite")
                else:
                    db.add(ExpensePayment(**payment_payload)); inserted["payments"] += 1
                history_id = f"IMP-P-{expense_id}"
                if not db.get(ExpenseApprovalHistory, history_id):
                    db.add(ExpenseApprovalHistory(history_id=history_id, expense_id=expense_id,
                        action="PAID", actor_id=row["approved_by"] or row["submitted_by"],
                        occurred_at=None, legacy_import=True))
                    inserted["approval_history"] += 1
    print("Task 11 import complete; existing records were preserved. Inserted: " +
          ", ".join(f"{key}={value}" for key, value in inserted.items()))
    print(f"Source warnings preserved: legacy self-approval records={report['legacy_warning_counts'].get('legacy_separation_of_duties_violations', 0)}")


if __name__ == "__main__":
    main()
