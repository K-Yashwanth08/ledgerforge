"""Vendor bill workflow and expense accounting integration."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .ledger_service import create_posted_journal
from .models import ChartOfAccount, ExpenseApprovalHistory, ExpenseBill, ExpensePayment, JournalLine, Vendor

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return (value if isinstance(value, Decimal) else Decimal(str(value or 0))).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_expense_account(db: Session, code: str) -> ChartOfAccount:
    account = db.get(ChartOfAccount, code)
    if not account or not account.is_active or account.is_group or account.account_type != "EXPENSE":
        raise HTTPException(422, f"Account {code} must be an active expense posting account")
    return account


def _named_account(db: Session, name: str, account_type: str) -> ChartOfAccount:
    matches = db.query(ChartOfAccount).filter(
        ChartOfAccount.account_name == name, ChartOfAccount.account_type == account_type,
        ChartOfAccount.is_group.is_(False), ChartOfAccount.is_active.is_(True)).all()
    if len(matches) != 1:
        raise HTTPException(503, f"Chart of accounts must define one active posting account named {name}")
    return matches[0]


def validate_vendor_account(db: Session, code: str):
    return validate_expense_account(db, code)


def duplicate_matches(db: Session, vendor_id: str, bill_reference: str,
                      expense_date, total_amount: Decimal, exclude_id: str | None = None):
    ref = bill_reference.strip().casefold()
    candidates = db.query(ExpenseBill).filter(ExpenseBill.vendor_id == vendor_id).all()
    exact, likely = [], []
    amount = money(total_amount)
    for candidate in candidates:
        if candidate.expense_id == exclude_id:
            continue
        same_ref = candidate.bill_reference.strip().casefold() == ref
        same_date = candidate.expense_date == expense_date
        same_amount = money(candidate.total_amount) == amount
        detail = {"expense_id": candidate.expense_id, "bill_reference": candidate.bill_reference,
                  "expense_date": candidate.expense_date.isoformat(), "total_amount": str(candidate.total_amount),
                  "ledger_entry_id": candidate.ledger_entry_id}
        if same_ref and same_date and same_amount:
            exact.append(detail)
        elif same_ref or (same_date and same_amount):
            likely.append(detail)
    return {"exact_duplicates": exact, "likely_duplicates": likely}


def _line_amounts(db: Session, entry_id: str):
    lines = db.query(JournalLine).filter_by(entry_id=entry_id).all()
    return {line.account_code: (money(line.debit), money(line.credit)) for line in lines}


def _ensure_entry(entry, expected: dict[str, tuple[Decimal, Decimal]], source_type: str, source_id: str, db: Session):
    if entry.source_type != source_type or entry.source_id != source_id or entry.status != "POSTED":
        raise HTTPException(409, "Existing journal entry does not match this bill operation")
    actual = {code: value for code, value in _line_amounts(db, entry.entry_id).items() if value != (ZERO, ZERO)}
    normalized = {code: value for code, value in expected.items() if value != (ZERO, ZERO)}
    if actual != normalized or entry.total_debit != entry.total_credit:
        raise HTTPException(409, "Existing journal entry differs from the expected balanced bill posting")


def approve_bill(db: Session, bill: ExpenseBill, actor_id: str):
    if bill.status != "SUBMITTED":
        raise HTTPException(409, "Only submitted bills can be approved")
    if bill.submitted_by == actor_id:
        raise HTTPException(403, "The bill submitter cannot approve their own bill")
    if bill.ledger_entry_id:
        raise HTTPException(409, "Submitted bill already has a ledger entry; reconcile it before approval")
    ap = _named_account(db, "Accounts Payable", "LIABILITY")
    gst_account = _named_account(db, "GST Input Credit", "ASSET") if bill.gst_amount > ZERO else None
    lines = [{"account_code": bill.category_account, "debit": bill.amount_excl_gst, "credit": ZERO,
              "line_description": f"Expense bill {bill.bill_reference}"}]
    expected = {bill.category_account: (money(bill.amount_excl_gst), ZERO),
                ap.account_code: (ZERO, money(bill.total_amount))}
    if gst_account:
        lines.append({"account_code": gst_account.account_code, "debit": bill.gst_amount, "credit": ZERO,
                      "line_description": f"Input GST for {bill.bill_reference}"})
        expected[gst_account.account_code] = (money(bill.gst_amount), ZERO)
    lines.append({"account_code": ap.account_code, "debit": ZERO, "credit": bill.total_amount,
                  "line_description": f"Accounts payable for {bill.bill_reference}"})
    entry = create_posted_journal(db, entry_date=bill.expense_date,
        description=f"Expense bill {bill.expense_id}: {bill.bill_reference}",
        source_type="EXPENSE", source_id=bill.expense_id, lines=lines, created_by=actor_id)
    _ensure_entry(entry, expected, "EXPENSE", bill.expense_id, db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bill.status = "APPROVED"
    bill.approved_by = actor_id
    bill.approved_at = now
    bill.ledger_entry_id = entry.entry_id
    db.add(ExpenseApprovalHistory(history_id=f"EA-{uuid4().hex[:28].upper()}", expense_id=bill.expense_id,
        action="APPROVED", actor_id=actor_id, occurred_at=now, legacy_import=False))
    return bill


def pay_bill(db: Session, bill: ExpenseBill, *, payment_date, payment_mode: str,
             cash_account_code: str, idempotency_key: str, reference_no: str | None, actor_id: str):
    cash = db.get(ChartOfAccount, cash_account_code)
    if (not cash or not cash.is_active or cash.is_group or cash.account_type != "ASSET"
            or not any(word in cash.account_name.casefold() for word in ("bank", "cash"))):
        raise HTTPException(422, "Select an active cash or bank posting account from the chart of accounts")
    replay = db.query(ExpensePayment).filter_by(idempotency_key=idempotency_key).first()
    if replay:
        same = (replay.expense_id == bill.expense_id and replay.payment_date == payment_date
                and replay.payment_mode == payment_mode and replay.cash_account_code == cash_account_code
                and replay.reference_no == reference_no and replay.amount == bill.total_amount)
        if not same:
            raise HTTPException(409, "Idempotency key was already used for a different payment")
        return replay
    if bill.status != "APPROVED":
        raise HTTPException(409, "A bill must be approved before it can be paid")
    if db.query(ExpensePayment).filter_by(expense_id=bill.expense_id).first():
        raise HTTPException(409, "This bill already has a recorded payment")
    ap = _named_account(db, "Accounts Payable", "LIABILITY")
    amount = money(bill.total_amount)
    lines = [
        {"account_code": ap.account_code, "debit": amount, "credit": ZERO,
         "line_description": f"Clear payable for {bill.bill_reference}"},
        {"account_code": cash.account_code, "debit": ZERO, "credit": amount,
         "line_description": f"Payment for {bill.bill_reference}"},
    ]
    entry = create_posted_journal(db, entry_date=payment_date,
        description=f"Expense payment {bill.expense_id}: {bill.bill_reference}",
        source_type="EXPENSE_PAYMENT", source_id=bill.expense_id, lines=lines, created_by=actor_id)
    _ensure_entry(entry, {ap.account_code: (amount, ZERO), cash.account_code: (ZERO, amount)},
                  "EXPENSE_PAYMENT", bill.expense_id, db)
    payment = ExpensePayment(payment_id=f"EP-{uuid4().hex[:28].upper()}", expense_id=bill.expense_id,
        payment_date=payment_date, amount=amount, cash_account_code=cash.account_code,
        payment_mode=payment_mode, reference_no=reference_no, ledger_entry_id=entry.entry_id,
        idempotency_key=idempotency_key)
    db.add(payment)
    bill.status = "PAID"
    bill.paid_date = payment_date
    bill.payment_mode = payment_mode
    bill.payment_ledger_entry_id = entry.entry_id
    db.add(ExpenseApprovalHistory(history_id=f"EA-{uuid4().hex[:28].upper()}", expense_id=bill.expense_id,
        action="PAID", actor_id=actor_id, occurred_at=datetime.now(timezone.utc).replace(tzinfo=None), legacy_import=False))
    return payment
