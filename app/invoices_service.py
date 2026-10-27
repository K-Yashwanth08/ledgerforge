from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import case, func, update
from sqlalchemy.orm import Session, selectinload
from .ledger_service import create_posted_journal, reverse_journal_entry
from .models import ChartOfAccount, Client, Invoice, InvoiceItem, InvoicePayment

CENT=Decimal("0.01"); ZERO=Decimal("0.00")
# These are the only invoice tax rates present in the supplied invoice dataset.
SUPPORTED_GST_RATES = {Decimal("0"), Decimal("18")}
INVOICE_TRANSITIONS = {
    "DRAFT": {"SENT", "OVERDUE", "CANCELLED"},
    "SENT": {"OVERDUE", "PARTIALLY_PAID", "PAID", "CANCELLED"},
    "OVERDUE": {"PARTIALLY_PAID", "PAID", "CANCELLED"},
    "PARTIALLY_PAID": {"OVERDUE", "PARTIALLY_PAID", "PAID"},
    "PAID": set(),
    "CANCELLED": set(),
}
def money(value):return Decimal(str(value)).quantize(CENT,rounding=ROUND_HALF_UP)

def _transition(invoice, target):
    if target not in INVOICE_TRANSITIONS.get(invoice.status, set()):
        raise HTTPException(409,f"Invoice cannot transition from {invoice.status} to {target}")
    invoice.status=target

def _validate_gst_rate(rate):
    value=Decimal(str(rate))
    if value not in SUPPORTED_GST_RATES:
        raise HTTPException(422,"gst_rate_percent must match a supplied invoice tax rate (0 or 18)")
    return value

def invoice_query(db):return db.query(Invoice).options(selectinload(Invoice.client),selectinload(Invoice.items),selectinload(Invoice.payments))
def invoice_detail(db,invoice_id):
    invoice=invoice_query(db).filter_by(invoice_id=invoice_id).first()
    if not invoice:raise HTTPException(404,"Invoice not found")
    return invoice

def _validate_items(db,items):
    clean=[]; subtotal=ZERO
    for no,item in enumerate(items,1):
        qty=Decimal(str(item.quantity)); price=Decimal(str(item.unit_price))
        if qty<=0 or price<0:raise HTTPException(422,"Invoice quantities must be positive and prices nonnegative")
        account=db.get(ChartOfAccount,item.revenue_account)
        if not account or not account.is_active or account.is_group or account.account_type!="INCOME":
            raise HTTPException(422,f"Revenue account {item.revenue_account} must be an active income account")
        amount=money(qty*price); subtotal+=amount
        clean.append({"line_no":no,"description":item.description.strip(),"quantity":qty,"unit_price":price,
            "amount":amount,"revenue_account":item.revenue_account})
    return clean,money(subtotal)

def _recalculate(db,invoice,items,rate):
    clean,subtotal=_validate_items(db,items)
    invoice.subtotal=subtotal;invoice.gst_rate_percent=_validate_gst_rate(rate)
    invoice.gst_amount=money(subtotal*invoice.gst_rate_percent/Decimal("100"))
    invoice.total_amount=invoice.subtotal+invoice.gst_amount
    invoice.balance_due=invoice.total_amount-invoice.amount_paid
    if invoice.balance_due<0:raise HTTPException(422,"New invoice total cannot be less than payments already recorded")
    invoice.service_line_account=clean[0]["revenue_account"]
    for old in list(invoice.items): db.delete(old)
    db.flush()
    invoice.items=[]
    invoice.items.extend([InvoiceItem(invoice_item_id=f"II-{uuid4().hex[:18].upper()}",**row) for row in clean])

def create_invoice(db:Session,payload,actor_id:str):
    if payload.due_date<payload.invoice_date:raise HTTPException(422,"due_date must be on or after invoice_date")
    if payload.currency!="INR":raise HTTPException(422,"Only INR invoices are supported by the configured ledger")
    client=db.get(Client,payload.client_id)
    if not client or not client.is_active:raise HTTPException(404,"Active client not found")
    if db.query(Invoice).filter_by(invoice_number=payload.invoice_number).first():raise HTTPException(409,"invoice_number already exists")
    clean,subtotal=_validate_items(db,payload.items)
    rate=_validate_gst_rate(payload.gst_rate_percent);gst=money(subtotal*rate/100)
    invoice=Invoice(invoice_id=f"INV-{uuid4().hex[:18].upper()}",invoice_number=payload.invoice_number,
        client_id=payload.client_id,invoice_date=payload.invoice_date,due_date=payload.due_date,
        service_line_account=clean[0]["revenue_account"],currency=payload.currency,subtotal=subtotal,
        gst_rate_percent=rate,gst_amount=gst,total_amount=subtotal+gst,amount_paid=ZERO,
        balance_due=subtotal+gst,status="DRAFT",last_payment_date=None,po_number=payload.po_number,
        carried_in_from_prior_period=False,created_by=actor_id,created_at=datetime.now(timezone.utc),ledger_entry_id=None)
    invoice.items=[InvoiceItem(invoice_item_id=f"II-{uuid4().hex[:18].upper()}",**row) for row in clean]
    db.add(invoice)
    try:db.flush();return invoice
    except Exception:db.rollback();raise

def update_draft_invoice(db:Session,invoice_id:str,payload):
    invoice=invoice_detail(db,invoice_id)
    if invoice.status!="DRAFT":raise HTTPException(409,"Only draft invoices can be edited")
    values=payload.model_dump(exclude_unset=True)
    for key in ("invoice_date","due_date","po_number"):
        if key in values:setattr(invoice,key,values[key])
    if invoice.due_date<invoice.invoice_date:raise HTTPException(422,"due_date must be on or after invoice_date")
    rate=values.get("gst_rate_percent",invoice.gst_rate_percent)
    items=payload.items if payload.items is not None else invoice.items
    if payload.items is not None:_recalculate(db,invoice,payload.items,rate)
    elif "gst_rate_percent" in values:
        _recalculate(db,invoice,invoice.items,rate)
    db.flush();return invoice

def send_invoice(db:Session,invoice_id:str,actor_id:str):
    invoice=invoice_detail(db,invoice_id)
    if invoice.status!="DRAFT":
        if invoice.status in {"SENT","OVERDUE","PARTIALLY_PAID","PAID"} and invoice.ledger_entry_id:
            return invoice
        raise HTTPException(409,"Only a draft invoice can be sent")
    if not invoice.items:raise HTTPException(422,"An invoice requires at least one line item")
    lines=[{"account_code":"1100","debit":invoice.total_amount,"credit":ZERO,"line_description":f"Receivable {invoice.invoice_number}"}]
    by_account={}
    for item in invoice.items:by_account[item.revenue_account]=by_account.get(item.revenue_account,ZERO)+item.amount
    for code,amount in sorted(by_account.items()):lines.append({"account_code":code,"debit":ZERO,"credit":amount,"line_description":f"Revenue {invoice.invoice_number}"})
    if invoice.gst_amount>0:lines.append({"account_code":"2200","debit":ZERO,"credit":invoice.gst_amount,"line_description":f"GST output {invoice.invoice_number}"})
    entry=create_posted_journal(db,entry_date=invoice.invoice_date,description=f"Invoice {invoice.invoice_number}",
        source_type="INVOICE",source_id=invoice.invoice_id,lines=lines,created_by=actor_id)
    invoice.ledger_entry_id=entry.entry_id
    _transition(invoice,"OVERDUE" if invoice.due_date<date.today() else "SENT")
    return invoice

def record_payment(db:Session,invoice_id:str,payload,actor_id:str):
    existing=db.query(InvoicePayment).filter_by(idempotency_key=payload.idempotency_key).first()
    if existing:
        if (existing.invoice_id!=invoice_id or existing.amount!=money(payload.amount)
                or existing.payment_date!=payload.payment_date or existing.payment_mode!=payload.payment_mode
                or existing.reference_no!=payload.reference_no):
            raise HTTPException(409,"idempotency_key was already used for a different payment")
        return existing
    invoice=invoice_detail(db,invoice_id)
    if invoice.status not in {"SENT","OVERDUE","PARTIALLY_PAID"}:
        raise HTTPException(409,f"Payments cannot be recorded for an invoice in {invoice.status} status")
    amount=money(payload.amount)
    if payload.payment_date<invoice.invoice_date:
        raise HTTPException(422,"payment_date must be on or after invoice_date")
    if amount<=0 or amount>invoice.balance_due:raise HTTPException(422,"Payment must be positive and no greater than the outstanding balance")
    payment_id=f"PAY-{uuid4().hex[:18].upper()}"
    entry=create_posted_journal(db,entry_date=payload.payment_date,description=f"Payment for invoice {invoice.invoice_number}",
        source_type="INVOICE_PAYMENT",source_id=payment_id,created_by=actor_id,lines=[
            {"account_code":"1001","debit":amount,"credit":ZERO,"line_description":f"Bank receipt {invoice.invoice_number}"},
            {"account_code":"1100","debit":ZERO,"credit":amount,"line_description":f"Receivable settlement {invoice.invoice_number}"}])
    payment=InvoicePayment(payment_id=payment_id,invoice_id=invoice_id,payment_date=payload.payment_date,amount=amount,
        payment_mode=payload.payment_mode,reference_no=payload.reference_no,received_by=actor_id,
        ledger_entry_id=entry.entry_id,idempotency_key=payload.idempotency_key)
    db.add(payment)
    target="PAID" if amount==invoice.balance_due else "PARTIALLY_PAID"
    _transition(invoice,target)
    changed=db.execute(update(Invoice).where(Invoice.invoice_id==invoice_id,
        Invoice.status.in_({"SENT","OVERDUE","PARTIALLY_PAID"}),Invoice.balance_due>=amount,
        Invoice.invoice_date<=payload.payment_date).values(
            amount_paid=Invoice.amount_paid+amount,balance_due=Invoice.balance_due-amount,
            last_payment_date=payload.payment_date,
            status=case((Invoice.balance_due==amount,"PAID"),else_="PARTIALLY_PAID")
        ).execution_options(synchronize_session=False))
    if changed.rowcount!=1:
        raise HTTPException(409,"Invoice balance or status changed while recording payment; retry with the same idempotency key")
    db.flush();return payment

def cancel_invoice(db:Session,invoice_id:str,reason:str,actor_id:str):
    invoice=invoice_detail(db,invoice_id)
    if invoice.status=="CANCELLED":return invoice
    if invoice.status=="DRAFT":_transition(invoice,"CANCELLED");return invoice
    if invoice.amount_paid>0:raise HTTPException(409,"An invoice with recorded payments cannot be cancelled; use a refund/credit-note workflow")
    if not invoice.ledger_entry_id:raise HTTPException(409,"Posted invoice has no linked journal entry to reverse")
    reverse_journal_entry(db,invoice.ledger_entry_id,date.today(),reason,actor_id)
    _transition(invoice,"CANCELLED")
    return invoice

def refresh_overdue(db:Session):
    q=db.query(Invoice).filter(Invoice.status.in_(["SENT","PARTIALLY_PAID"]),Invoice.balance_due>0,Invoice.due_date<date.today())
    q.update({Invoice.status:"OVERDUE"},synchronize_session=False)

def receivables_by_client(db:Session):
    rows=db.query(Client.client_id,Client.client_name,func.coalesce(func.sum(Invoice.balance_due),0)).join(
        Invoice,Invoice.client_id==Client.client_id).filter(Invoice.status.in_(["SENT","OVERDUE","PARTIALLY_PAID"]),Invoice.balance_due>0).group_by(Client.client_id,Client.client_name).order_by(Client.client_name).all()
    return [{"client_id":r[0],"client_name":r[1],"outstanding_balance":Decimal(str(r[2]))} for r in rows]
