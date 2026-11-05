from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session

from ..database import get_db
from ..expense_service import (approve_bill, duplicate_matches, money, pay_bill,
                               validate_expense_account, validate_vendor_account)
from ..models import (Department, ExpenseApprovalHistory, ExpenseBill, ExpensePayment,
                      Vendor)
from ..schemas import (ExpenseBillCreate, ExpenseBillOut, ExpenseDuplicateCheck,
                       ExpensePaymentCreate, VendorCreate, VendorOut, VendorPatch)
from ..security import admin_actor, hr_actor

router = APIRouter(tags=["vendors and expense bills"])
ZERO = Decimal("0.00")


def _bill_out(db: Session, bill: ExpenseBill):
    history = db.query(ExpenseApprovalHistory).filter_by(expense_id=bill.expense_id).order_by(
        case((ExpenseApprovalHistory.action == "SUBMITTED", 1),
             (ExpenseApprovalHistory.action == "APPROVED", 2),
             (ExpenseApprovalHistory.action == "PAID", 3), else_=4),
        ExpenseApprovalHistory.occurred_at, ExpenseApprovalHistory.history_id).all()
    return {**{key: getattr(bill, key) for key in (
        "expense_id", "expense_date", "category_account", "vendor_id", "bill_reference", "description",
        "department_id", "amount_excl_gst", "gst_rate_percent", "gst_amount", "total_amount", "due_date",
        "paid_date", "status", "source_status", "payment_mode", "submitted_by", "approved_by", "approved_at",
        "ledger_entry_id", "payment_ledger_entry_id", "legacy_sod_violation")},
        "approval_history": [{"action": item.action, "actor_id": item.actor_id,
            "occurred_at": item.occurred_at, "legacy_import": item.legacy_import} for item in history]}


def _date_filters(start_date, end_date):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")


def _recognized_bills(db: Session, start_date=None, end_date=None):
    _date_filters(start_date, end_date)
    query = db.query(ExpenseBill).filter(ExpenseBill.status.in_(["APPROVED", "PAID"]),
                                         ExpenseBill.ledger_entry_id.is_not(None))
    if start_date: query = query.filter(ExpenseBill.expense_date >= start_date)
    if end_date: query = query.filter(ExpenseBill.expense_date <= end_date)
    return query.order_by(ExpenseBill.expense_date, ExpenseBill.expense_id).all()


@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(search: str | None = None, active_only: bool | None = None,
                 limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    query = db.query(Vendor)
    if search: query = query.filter(Vendor.vendor_name.ilike(f"%{search.strip()}%"))
    if active_only is not None: query = query.filter(Vendor.is_active.is_(active_only))
    return query.order_by(Vendor.vendor_name, Vendor.vendor_id).offset(offset).limit(limit).all()


@router.post("/vendors", response_model=VendorOut, status_code=201)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    if db.get(Vendor, payload.vendor_id): raise HTTPException(409, "vendor_id already exists")
    validate_vendor_account(db, payload.primary_expense_account)
    vendor = Vendor(**payload.model_dump())
    db.add(vendor)
    try: db.commit(); db.refresh(vendor); return vendor
    except Exception: db.rollback(); raise


@router.get("/vendors/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor: raise HTTPException(404, "Vendor not found")
    return vendor


@router.patch("/vendors/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: str, payload: VendorPatch, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor: raise HTTPException(404, "Vendor not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("primary_expense_account"):
        validate_vendor_account(db, changes["primary_expense_account"])
    for key, value in changes.items(): setattr(vendor, key, value)
    try: db.commit(); db.refresh(vendor); return vendor
    except Exception: db.rollback(); raise


@router.post("/expenses/duplicate-check")
def check_bill_duplicates(payload: ExpenseDuplicateCheck, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    if not db.get(Vendor, payload.vendor_id): raise HTTPException(404, "Vendor not found")
    return duplicate_matches(db, payload.vendor_id, payload.bill_reference, payload.expense_date, payload.total_amount)


@router.get("/expenses/reports/monthly")
def monthly_expense_report(start_date: date | None = None, end_date: date | None = None,
                           db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    monthly = defaultdict(lambda: {"bill_count": 0, "amount_excl_gst": ZERO, "gst_amount": ZERO, "total_amount": ZERO})
    for bill in _recognized_bills(db, start_date, end_date):
        row = monthly[bill.expense_date.strftime("%Y-%m")]
        row["bill_count"] += 1
        for key in ("amount_excl_gst", "gst_amount", "total_amount"): row[key] += money(getattr(bill, key))
    return {"start_date": start_date, "end_date": end_date,
            "months": [{"month": month, **values} for month, values in sorted(monthly.items())],
            "totals": {key: sum((item[key] for item in monthly.values()), ZERO)
                       for key in ("amount_excl_gst", "gst_amount", "total_amount")}}


@router.get("/expenses/reports/vendor-wise")
def vendor_expense_report(start_date: date | None = None, end_date: date | None = None,
                          db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    totals = defaultdict(lambda: {"bill_count": 0, "amount_excl_gst": ZERO, "gst_amount": ZERO, "total_amount": ZERO})
    names = {}
    for bill in _recognized_bills(db, start_date, end_date):
        row = totals[bill.vendor_id]; names[bill.vendor_id] = bill.vendor.vendor_name; row["bill_count"] += 1
        for key in ("amount_excl_gst", "gst_amount", "total_amount"): row[key] += money(getattr(bill, key))
    return [{"vendor_id": key, "vendor_name": names[key], **values}
            for key, values in sorted(totals.items(), key=lambda item: names[item[0]].casefold())]


@router.get("/expenses/reports/outstanding")
def outstanding_expense_report(db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    bills = db.query(ExpenseBill).filter_by(status="APPROVED").order_by(ExpenseBill.due_date, ExpenseBill.expense_id).all()
    return [{"expense_id": bill.expense_id, "vendor_id": bill.vendor_id,
        "vendor_name": bill.vendor.vendor_name, "bill_reference": bill.bill_reference,
        "expense_date": bill.expense_date, "due_date": bill.due_date,
        "amount_excl_gst": bill.amount_excl_gst, "gst_amount": bill.gst_amount,
        "outstanding_amount": bill.total_amount} for bill in bills]


@router.get("/expenses/reports/paid-unpaid")
def expense_payment_status_report(db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    result = {}
    for status in ("PAID", "APPROVED", "SUBMITTED"):
        bills = db.query(ExpenseBill).filter_by(status=status).all()
        result[status.lower()] = {"bill_count": len(bills),
            "amount_excl_gst": sum((money(b.amount_excl_gst) for b in bills), ZERO),
            "gst_amount": sum((money(b.gst_amount) for b in bills), ZERO),
            "total_amount": sum((money(b.total_amount) for b in bills), ZERO)}
    return result


@router.get("/expenses")
def list_expenses(vendor_id: str | None = None, status: str | None = None,
                  start_date: date | None = None, end_date: date | None = None,
                  limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    _date_filters(start_date, end_date)
    query = db.query(ExpenseBill)
    if vendor_id: query = query.filter(ExpenseBill.vendor_id == vendor_id)
    if status:
        normalized = "APPROVED" if status.upper() == "UNPAID" else status.upper()
        query = query.filter(ExpenseBill.status == normalized)
    if start_date: query = query.filter(ExpenseBill.expense_date >= start_date)
    if end_date: query = query.filter(ExpenseBill.expense_date <= end_date)
    return [_bill_out(db, bill) for bill in query.order_by(ExpenseBill.expense_date.desc(), ExpenseBill.expense_id)
            .offset(offset).limit(limit).all()]


@router.post("/expenses", status_code=201)
def create_expense_bill(payload: ExpenseBillCreate, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    vendor = db.get(Vendor, payload.vendor_id)
    if not vendor or not vendor.is_active: raise HTTPException(422, "Vendor must exist and be active")
    validate_expense_account(db, payload.category_account)
    if payload.department_id and not db.get(Department, payload.department_id): raise HTTPException(422, "Department not found")
    excl = money(payload.amount_excl_gst)
    gst = money(excl * payload.gst_rate_percent / Decimal("100"))
    total = excl + gst
    matches = duplicate_matches(db, payload.vendor_id, payload.bill_reference, payload.expense_date, total)
    if matches["exact_duplicates"]:
        raise HTTPException(409, {"message": "Exact duplicate bill already exists", **matches})
    bill_values = payload.model_dump()
    bill_values.update(amount_excl_gst=excl, gst_amount=gst, total_amount=total)
    bill = ExpenseBill(expense_id=f"EXP-{uuid4().hex[:24].upper()}", **bill_values,
        status="SUBMITTED",
        source_status=None, payment_mode=None, submitted_by=actor["sub"], approved_by=None,
        approved_at=None, paid_date=None, ledger_entry_id=None, payment_ledger_entry_id=None,
        legacy_sod_violation=False)
    db.add(bill)
    db.add(ExpenseApprovalHistory(history_id=f"EA-{uuid4().hex[:28].upper()}", expense_id=bill.expense_id,
        action="SUBMITTED", actor_id=actor["sub"], occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        legacy_import=False))
    try:
        db.commit(); db.refresh(bill)
        result = _bill_out(db, bill)
        result["duplicate_warnings"] = matches["likely_duplicates"]
        if payload.category_account != vendor.primary_expense_account:
            result["account_mapping_warning"] = {"vendor_primary": vendor.primary_expense_account,
                                                  "bill_category": payload.category_account}
        return result
    except Exception: db.rollback(); raise


@router.get("/expenses/{expense_id}")
def get_expense_bill(expense_id: str, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    bill = db.get(ExpenseBill, expense_id)
    if not bill: raise HTTPException(404, "Expense bill not found")
    return _bill_out(db, bill)


@router.post("/expenses/{expense_id}/approve")
def approve_expense_bill(expense_id: str, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    bill = db.get(ExpenseBill, expense_id)
    if not bill: raise HTTPException(404, "Expense bill not found")
    try:
        bill = approve_bill(db, bill, actor["sub"]); db.commit(); db.refresh(bill)
        return _bill_out(db, bill)
    except Exception: db.rollback(); raise


@router.post("/expenses/{expense_id}/payments", status_code=201)
def pay_expense_bill(expense_id: str, payload: ExpensePaymentCreate,
                     db: Session = Depends(get_db), actor: dict = Depends(admin_actor)):
    bill = db.get(ExpenseBill, expense_id)
    if not bill: raise HTTPException(404, "Expense bill not found")
    try:
        payment = pay_bill(db, bill, payment_date=payload.payment_date, payment_mode=payload.payment_mode,
            cash_account_code=payload.cash_account_code, idempotency_key=payload.idempotency_key,
            reference_no=payload.reference_no, actor_id=actor["sub"])
        db.commit(); db.refresh(payment)
        return {key: getattr(payment, key) for key in ("payment_id", "expense_id", "payment_date", "amount",
            "cash_account_code", "payment_mode", "reference_no", "ledger_entry_id", "idempotency_key")}
    except Exception: db.rollback(); raise
