"""Idempotently load chart-of-accounts and posted-journal source snapshots."""
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from app.config import settings
from app.database import SessionLocal
from app.models import ChartOfAccount, JournalEntry, JournalLine
from scripts.load_phase2_task6 import BATCH_SIZE, conflict_safe_insert

DATA=Path(settings.data_dir)
def rows(filename):
    path=DATA/filename
    if not path.is_file(): raise FileNotFoundError(f"Required accounting source CSV is missing: {path}")
    with path.open(encoding="utf-8-sig",newline="") as f: yield from csv.DictReader(f)
def dec(value): return Decimal(value or "0")
def account_code(value):
    if not value:return None
    n=Decimal(value)
    return str(n.quantize(Decimal("1"))) if n==n.to_integral_value() else value
def batches(filename,convert):
    batch=[]
    for row in rows(filename):
        batch.append(convert(row))
        if len(batch)>=BATCH_SIZE:yield batch;batch=[]
    if batch:yield batch

def main():
    with SessionLocal.begin() as db:
        accounts=0
        for batch in batches("chart_of_accounts.csv",lambda r:{**r,"parent_code":account_code(r["parent_code"]),
            "is_group":r["is_group"]=="Y","is_active":r["is_active"]=="Y"}):accounts+=conflict_safe_insert(db,ChartOfAccount,batch)
        entries=0
        for batch in batches("journal_entries.csv",lambda r:{**r,"entry_date":date.fromisoformat(r["entry_date"]),
            "total_debit":dec(r["total_debit"]),"total_credit":dec(r["total_credit"]),"source_id":r["source_id"] or None,
            "reversal_of_source_id":r["reversal_of_source_id"] or None,"created_by":r["created_by"] or None,
            "created_at":datetime.fromisoformat(r["created_at"]) if r["created_at"] else None}):entries+=conflict_safe_insert(db,JournalEntry,batch)
        lines=0
        for batch in batches("journal_lines.csv",lambda r:{**r,"line_no":int(r["line_no"]),"debit":dec(r["debit"]),
            "credit":dec(r["credit"]),"account_code":account_code(r["account_code"]),
            "cost_center_department_id":r["cost_center_department_id"] or None,"line_description":r["line_description"] or ""}):lines+=conflict_safe_insert(db,JournalLine,batch)
    print(f"Task 9 import complete: accounts={accounts}, journal entries={entries}, journal lines={lines}; existing IDs preserved.")
if __name__=="__main__":main()
