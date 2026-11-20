from datetime import date
from ..export_utils import csv_download, validate_date_filters
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..ledger_service import account_balance, create_journal_entry, post_payroll_run, reverse_journal_entry
from ..models import ChartOfAccount, JournalEntry, JournalLine, PayrollRun
from ..schemas import AccountBalanceOut, AccountOut, JournalEntryCreate, JournalEntryOut, ReversalCreate
from ..security import admin_actor, hr_actor

router=APIRouter(prefix="/ledger",tags=["accounting ledger"])

def _out(db,entry):
    return {"entry_id":entry.entry_id,"entry_date":entry.entry_date,"posting_period":entry.posting_period,
        "financial_year":entry.financial_year,"description":entry.description,"source_type":entry.source_type,
        "source_id":entry.source_id,"status":entry.status,"total_debit":entry.total_debit,
        "total_credit":entry.total_credit,"reversal_of_source_id":entry.reversal_of_source_id,
        "lines":db.query(JournalLine).filter_by(entry_id=entry.entry_id).order_by(JournalLine.line_no).all()}

@router.get("/accounts",response_model=list[AccountOut])
def accounts(active_only:bool=True,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    q=db.query(ChartOfAccount)
    if active_only:q=q.filter(ChartOfAccount.is_active.is_(True))
    return q.order_by(ChartOfAccount.account_code).all()

@router.get("/accounts/{account_code}/balance",response_model=AccountBalanceOut)
def balance(account_code:str,as_of:date=Query(default_factory=date.today),db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    return account_balance(db,account_code,as_of)

@router.get("/journal-entries",response_model=list[JournalEntryOut])
def entries(start_date:date|None=None,end_date:date|None=None,status:str|None="POSTED",
            source_type:str|None=None,account_code:str|None=None,
            limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),
            db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    if start_date and end_date and end_date<start_date:raise HTTPException(422,"end_date must be on or after start_date")
    q=db.query(JournalEntry)
    if start_date:q=q.filter(JournalEntry.entry_date>=start_date)
    if end_date:q=q.filter(JournalEntry.entry_date<=end_date)
    if status:q=q.filter(JournalEntry.status==status.upper())
    if source_type:q=q.filter(JournalEntry.source_type==source_type.upper())
    if account_code:q=q.join(JournalLine,JournalLine.entry_id==JournalEntry.entry_id).filter(JournalLine.account_code==account_code).distinct()
    result=q.order_by(JournalEntry.entry_date.desc(),JournalEntry.entry_id).offset(offset).limit(limit).all()
    return [_out(db,e) for e in result]

@router.get("/journal-entries.csv", include_in_schema=True)
def export_entries(start_date: date | None = None, end_date: date | None = None,
                   since: date | None = Query(None, description="Inclusive journal-entry date watermark"),
                   status: str | None = "POSTED", db: Session = Depends(get_db),
                   _actor: dict = Depends(hr_actor)):
    validate_date_filters(start_date, end_date, since)
    query = db.query(JournalEntry)
    lower = since or start_date
    if lower:
        query = query.filter(JournalEntry.entry_date >= lower)
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
    if status:
        query = query.filter(JournalEntry.status == status.upper())
    query = query.order_by(JournalEntry.entry_date, JournalEntry.entry_id)
    columns = ("entry_id", "entry_date", "posting_period", "financial_year", "description",
        "source_type", "source_id", "status", "total_debit", "total_credit", "reversal_of_source_id")
    return csv_download("ledgerforge-ledger.csv", columns,
        ({key: getattr(entry, key) for key in columns} for entry in query.yield_per(1000)))

@router.get("/journal-entries/{entry_id}",response_model=JournalEntryOut)
def entry_detail(entry_id:str,db:Session=Depends(get_db),_actor:dict=Depends(hr_actor)):
    entry=db.get(JournalEntry,entry_id)
    if not entry:raise HTTPException(404,"Journal entry not found")
    return _out(db,entry)

@router.post("/journal-entries",response_model=JournalEntryOut,status_code=201)
def create_entry(payload:JournalEntryCreate,db:Session=Depends(get_db),actor:dict=Depends(admin_actor)):
    try:
        entry=create_journal_entry(db,payload,actor["sub"]);db.commit();db.refresh(entry);return _out(db,entry)
    except Exception:
        db.rollback();raise

@router.post("/journal-entries/{entry_id}/reverse",response_model=JournalEntryOut,status_code=201)
def reverse_entry(entry_id:str,payload:ReversalCreate,db:Session=Depends(get_db),actor:dict=Depends(admin_actor)):
    try:
        entry=reverse_journal_entry(db,entry_id,payload.entry_date,payload.reason,actor["sub"])
        db.commit();db.refresh(entry);return _out(db,entry)
    except Exception:
        db.rollback();raise

@router.post("/payroll-runs/{run_id}/post",response_model=JournalEntryOut,status_code=201)
def post_payroll(run_id:str,db:Session=Depends(get_db),actor:dict=Depends(admin_actor)):
    try:
        run=db.get(PayrollRun,run_id)
        if not run:raise HTTPException(404,"Payroll run not found")
        existing=db.query(JournalEntry).filter_by(source_type="PAYROLL_RUN",source_id=run_id,status="POSTED").first()
        if not existing and run.status!="APPROVED":
            raise HTTPException(409,"Payroll must be approved before it can be posted to the ledger")
        entry=post_payroll_run(db,run_id,actor["sub"]);db.commit();db.refresh(entry);return _out(db,entry)
    except Exception:
        db.rollback();raise
