from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import ChartOfAccount, JournalEntry, JournalLine, PayrollItem, PayrollRun

ZERO=Decimal("0.00")
def fiscal_year(d):
    y=d.year if d.month>=4 else d.year-1
    return f"FY{y}-{(y+1)%100:02d}"

def _entry(db,*,entry_date,description,source_type,source_id,lines,created_by,reversal_of_source_id=None):
    if len(lines)<2: raise HTTPException(422,"A journal entry requires at least two lines")
    debit=credit=ZERO
    normalized=[]
    for no,line in enumerate(lines,1):
        code=line["account_code"]; account=db.get(ChartOfAccount,code)
        if not account or not account.is_active or account.is_group:
            raise HTTPException(422,f"Account {code} is missing, inactive, or a group account")
        dr=Decimal(str(line.get("debit",0))); cr=Decimal(str(line.get("credit",0)))
        if dr<0 or cr<0 or (dr==0)==(cr==0):
            raise HTTPException(422,"Each journal line must contain exactly one positive debit or credit")
        debit+=dr; credit+=cr
        normalized.append({"line_id":f"JL-{uuid4().hex[:18].upper()}","line_no":no,"account_code":code,
            "debit":dr,"credit":cr,"cost_center_department_id":line.get("cost_center_department_id"),
            "line_description":line.get("line_description","") or description})
    if debit==0 or credit==0 or debit!=credit:
        raise HTTPException(422,f"Journal entry is unbalanced: debits {debit:.2f}, credits {credit:.2f}")
    if source_id:
        existing=db.query(JournalEntry).filter_by(source_type=source_type,source_id=source_id,status="POSTED").first()
        if existing:return existing
    entry=JournalEntry(entry_id=f"JE-{uuid4().hex[:18].upper()}",entry_date=entry_date,
        posting_period=entry_date.strftime("%Y-%m"),financial_year=fiscal_year(entry_date),description=description,
        source_type=source_type,source_id=source_id,status="POSTED",total_debit=debit,total_credit=credit,
        reversal_of_source_id=reversal_of_source_id,created_by=created_by,created_at=datetime.now(timezone.utc))
    db.add(entry); db.flush()
    db.add_all([JournalLine(entry_id=entry.entry_id,**line) for line in normalized]); db.flush()
    return entry

def create_journal_entry(db:Session,payload,created_by:str):
    return _entry(db,entry_date=payload.entry_date,description=payload.description,source_type=payload.source_type,
        source_id=payload.source_id,lines=[x.model_dump() for x in payload.lines],created_by=created_by)

def create_posted_journal(db:Session,*,entry_date,description,source_type,source_id,lines,created_by):
    return _entry(db,entry_date=entry_date,description=description,source_type=source_type,
        source_id=source_id,lines=lines,created_by=created_by)

def reverse_journal_entry(db:Session,entry_id:str,entry_date:date,reason:str,created_by:str):
    original=db.get(JournalEntry,entry_id)
    if not original:raise HTTPException(404,"Journal entry not found")
    if original.status!="POSTED":raise HTTPException(409,"Only posted entries can be reversed")
    existing=db.query(JournalEntry).filter_by(source_type="REVERSAL",source_id=entry_id,status="POSTED").first()
    if existing:raise HTTPException(409,"This journal entry has already been reversed")
    source_lines=db.query(JournalLine).filter_by(entry_id=entry_id).order_by(JournalLine.line_no).all()
    lines=[{"account_code":x.account_code,"debit":x.credit,"credit":x.debit,
        "cost_center_department_id":x.cost_center_department_id,"line_description":f"Reversal: {reason}"} for x in source_lines]
    return _entry(db,entry_date=entry_date,description=f"Reversal of {entry_id}: {reason}",source_type="REVERSAL",
        source_id=entry_id,lines=lines,created_by=created_by,reversal_of_source_id=entry_id)

def account_balance(db:Session,account_code:str,as_of:date):
    account=db.get(ChartOfAccount,account_code)
    if not account:raise HTTPException(404,"Account not found")
    totals=db.query(func.coalesce(func.sum(JournalLine.debit),0),func.coalesce(func.sum(JournalLine.credit),0)).join(
        JournalEntry,JournalEntry.entry_id==JournalLine.entry_id).filter(JournalLine.account_code==account_code,
        JournalEntry.status=="POSTED",JournalEntry.entry_date<=as_of).one()
    debit,credit=Decimal(str(totals[0])),Decimal(str(totals[1]))
    normal=debit-credit if account.normal_balance.upper()=="DEBIT" else credit-debit
    return {"account_code":account_code,"account_name":account.account_name,"as_of":as_of,
        "normal_balance":account.normal_balance,"debits":debit,"credits":credit,"balance":normal}

def post_payroll_run(db:Session,run_id:str,posted_by:str):
    run=db.get(PayrollRun,run_id)
    if not run:raise HTTPException(404,"Payroll run not found")
    existing=db.query(JournalEntry).filter_by(source_type="PAYROLL_RUN",source_id=run_id,status="POSTED").first()
    if existing:return existing
    items=db.query(PayrollItem).filter_by(run_id=run_id).all()
    if not items:raise HTTPException(422,"Payroll run has no stored payroll items")
    totals={k:sum((Decimal(getattr(i,k) or 0) for i in items),ZERO) for k in (
        "earned_fixed_pay","overtime_pay","variable_pay","pf_employee","esi_employee","professional_tax",
        "tds","other_deductions","net_pay","pf_employer","esi_employer")}
    lines=[]
    for code,key,label in [("5001","earned_fixed_pay","Fixed payroll expense"),("5002","overtime_pay","Overtime expense"),
        ("5003","variable_pay","Variable pay expense"),("5004","pf_employer","Employer PF expense"),("5005","esi_employer","Employer ESI expense")]:
        if totals[key]>0:lines.append({"account_code":code,"debit":totals[key],"credit":ZERO,"line_description":label})
    liability=[("2100",totals["net_pay"],"Net salaries payable"),
        ("2110",totals["pf_employee"]+totals["pf_employer"],"PF payable"),
        ("2120",totals["esi_employee"]+totals["esi_employer"],"ESI payable"),
        ("2130",totals["tds"],"TDS payable"),("2140",totals["professional_tax"],"Professional tax payable"),
        ("1300",totals["other_deductions"],"Employee advances and loan recoveries")]
    for code,amount,label in liability:
        if amount>0:lines.append({"account_code":code,"debit":ZERO,"credit":amount,"line_description":label})
    date_for_entry=run.pay_date or run.period_end
    entry=_entry(db,entry_date=date_for_entry,description=f"Payroll run {run_id}",source_type="PAYROLL_RUN",
        source_id=run_id,lines=lines,created_by=posted_by)
    run.journal_entry_id=entry.entry_id
    run.status="POSTED"
    return entry
