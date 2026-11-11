"""Idempotently load supplied client/invoice/payment source snapshots."""
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import Client, Invoice, InvoiceItem, InvoicePayment
from scripts.load_phase2_task6 import BATCH_SIZE, conflict_safe_insert
from scripts.load_phase2_task9 import account_code

DATA=Path(settings.data_dir)
def rows(filename):
    path=DATA/filename
    if not path.is_file():raise FileNotFoundError(f"Required receivables source CSV is missing: {path}")
    with path.open(encoding="utf-8-sig",newline="") as f:yield from csv.DictReader(f)
def dec(value):return Decimal(value or "0")
def batches(filename,convert):
    batch=[]
    for row in rows(filename):
        batch.append(convert(row))
        if len(batch)>=BATCH_SIZE:yield batch;batch=[]
    if batch:yield batch

def main():
    with SessionLocal.begin() as db:
        client_count=0
        for batch in batches("clients.csv",lambda r:{**r,"is_active":r["is_active"]=="Y",
            "payment_terms_days":int(r["payment_terms_days"]),"onboarded_on":date.fromisoformat(r["onboarded_on"]) if r["onboarded_on"] else None,
            **{k:r[k] or None for k in ("industry","city","state_or_region","client_type","gst_registration","payment_behaviour","primary_service_line","contact_email")}}):client_count+=conflict_safe_insert(db,Client,batch)
        invoice_count=0
        for batch in batches("invoices.csv",lambda r:{**r,"invoice_date":date.fromisoformat(r["invoice_date"]),"due_date":date.fromisoformat(r["due_date"]),
            "last_payment_date":date.fromisoformat(r["last_payment_date"]) if r["last_payment_date"] else None,
            **{k:dec(r[k]) for k in ("subtotal","gst_rate_percent","gst_amount","total_amount","amount_paid","balance_due")},
            "service_line_account":account_code(r["service_line_account"]),"carried_in_from_prior_period":r["carried_in_from_prior_period"]=="Y",
            "created_by":r["created_by"] or None,"created_at":datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
            "ledger_entry_id":r["ledger_entry_id"] or None}):invoice_count+=conflict_safe_insert(db,Invoice,batch)
        item_count=0
        for batch in batches("invoice_items.csv",lambda r:{**r,"line_no":int(r["line_no"]),"quantity":dec(r["quantity"]),"unit_price":dec(r["unit_price"]),
            "amount":dec(r["amount"]),"revenue_account":account_code(r["revenue_account"])}):item_count+=conflict_safe_insert(db,InvoiceItem,batch)
        payment_count=0
        for batch in batches("invoice_payments.csv",lambda r:{**r,"payment_date":date.fromisoformat(r["payment_date"]),"amount":dec(r["amount"]),
            "reference_no":r["reference_no"] or None,"received_by":r["received_by"] or None,"ledger_entry_id":r["ledger_entry_id"] or None,
            "idempotency_key":f"imported:{r['payment_id']}"}):payment_count+=conflict_safe_insert(db,InvoicePayment,batch)
    print(f"Task 10 import complete: clients={client_count}, invoices={invoice_count}, items={item_count}, payments={payment_count}; existing IDs preserved.")
if __name__=="__main__":main()
