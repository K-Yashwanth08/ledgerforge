from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.database import Base,get_db
from app.main import app
from app.models import (ChartOfAccount,Client,Department,Employee,Invoice,InvoicePayment,JournalEntry,
                        JournalLine,PayrollItem,PayrollRun,Role)
from tests.test_attendance_leave import token

@pytest.fixture
def finance_client(monkeypatch):
    monkeypatch.setattr(settings,"secret_key","test-only-signing-secret-at-least-32-bytes")
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine);Factory=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    accounts=[("1001","Bank","ASSET","DEBIT"),("1100","Receivables","ASSET","DEBIT"),
        ("1300","Advances","ASSET","DEBIT"),("2100","Salaries Payable","LIABILITY","CREDIT"),
        ("2110","PF Payable","LIABILITY","CREDIT"),("2120","ESI Payable","LIABILITY","CREDIT"),
        ("2130","TDS Payable","LIABILITY","CREDIT"),("2140","PT Payable","LIABILITY","CREDIT"),
        ("2200","GST Payable","LIABILITY","CREDIT"),("4001","Revenue","INCOME","CREDIT"),
        ("5001","Wages","EXPENSE","DEBIT"),("5002","OT","EXPENSE","DEBIT"),
        ("5003","Bonus","EXPENSE","DEBIT"),("5004","PF Expense","EXPENSE","DEBIT"),("5005","ESI Expense","EXPENSE","DEBIT")]
    with Factory.begin() as db:
        db.add(Department(department_id="D1",department_name="Test",cost_center="CC1"))
        db.add(Role(role_id="R1",department_id="D1",role_title="Engineer",level=1,grade="L1",band_min_annual=1,band_mid_annual=2,band_max_annual=3,overtime_eligible="N",band_year=2026))
        db.add(Employee(employee_id="E1",first_name="Test",last_name="Person",full_name="Test Person",work_email="e1@example.test",hire_date=date(2020,1,1),employment_status="Active",employment_type="Permanent",department_id="D1",role_id="R1"))
        db.add_all([ChartOfAccount(account_code=c,account_name=n,account_type=t,normal_balance=bal,parent_code=None,is_group=False,statement="P&L",is_active=True) for c,n,t,bal in accounts])
        db.add(Client(client_id="C1",client_name="Test Client",country="India",payment_terms_days=30,is_active=True))
    session=Factory()
    def override():yield session
    app.dependency_overrides[get_db]=override
    with TestClient(app) as client:yield client,session
    app.dependency_overrides.clear();session.close();Base.metadata.drop_all(engine);engine.dispose()

def hr():return {"Authorization":f"Bearer {token('HR1','hr')}"}

def journal_body(debit="100.00",credit="100.00",account="4001"):
    return {"entry_date":"2026-01-15","description":"Test journal","source_type":"MANUAL","lines":[
        {"account_code":"1100","debit":debit,"credit":"0","line_description":"AR"},
        {"account_code":account,"debit":"0","credit":credit,"line_description":"Revenue"}]}

def test_balanced_entry_unbalanced_and_invalid_account(finance_client):
    client,db=finance_client
    ok=client.post("/ledger/journal-entries",json=journal_body(),headers=hr())
    assert ok.status_code==201 and ok.json()["total_debit"]=="100.00"
    assert client.post("/ledger/journal-entries",json=journal_body("100","99"),headers=hr()).status_code==422
    assert client.post("/ledger/journal-entries",json=journal_body(account="9999"),headers=hr()).status_code==422
    assert db.query(JournalEntry).count()==1 and db.query(JournalLine).count()==2

def test_journal_entries_can_filter_by_account(finance_client):
    client,_=finance_client
    client.post("/ledger/journal-entries",json=journal_body(),headers=hr())
    client.post("/ledger/journal-entries",json={**journal_body(),"entry_date":"2026-01-16",
        "lines":[{"account_code":"1001","debit":"75.00","credit":"0"},
                 {"account_code":"4001","debit":"0","credit":"75.00"}]},headers=hr())
    rows=client.get("/ledger/journal-entries?account_code=1100",headers=hr()).json()
    assert len(rows)==1 and rows[0]["lines"][0]["account_code"]=="1100"

def test_failed_journal_flush_rolls_back_entry(finance_client):
    client,db=finance_client
    def fail_line_flush(session,flush_context,instances):
        if any(isinstance(obj,JournalLine) for obj in session.new):
            raise RuntimeError("simulated journal line write failure")
    event.listen(db,"before_flush",fail_line_flush)
    try:
        with TestClient(app,raise_server_exceptions=False) as isolated_client:
            response=isolated_client.post("/ledger/journal-entries",json=journal_body(),headers=hr())
    finally:
        event.remove(db,"before_flush",fail_line_flush)
    assert response.status_code==500
    assert db.query(JournalEntry).count()==0
    assert db.query(JournalLine).count()==0

def test_posted_entry_reversal_and_account_normal_balance(finance_client):
    client,db=finance_client
    entry=client.post("/ledger/journal-entries",json=journal_body(),headers=hr()).json()
    before=client.get("/ledger/accounts/1100/balance?as_of=2026-01-31",headers=hr()).json()
    assert before["balance"]=="100.00"
    rev=client.post(f"/ledger/journal-entries/{entry['entry_id']}/reverse",json={"entry_date":"2026-02-01","reason":"Correction"},headers=hr())
    assert rev.status_code==201 and rev.json()["total_debit"]==rev.json()["total_credit"]
    assert client.post(f"/ledger/journal-entries/{entry['entry_id']}/reverse",json={"entry_date":"2026-02-02","reason":"Again"},headers=hr()).status_code==409
    after=client.get("/ledger/accounts/1100/balance?as_of=2026-02-02",headers=hr()).json()
    assert after["balance"]=="0.00"
    assert client.patch(f"/ledger/journal-entries/{entry['entry_id']}",json={},headers=hr()).status_code==405
    assert client.delete(f"/ledger/journal-entries/{entry['entry_id']}",headers=hr()).status_code==405

def test_payroll_post_is_balanced_and_idempotent(finance_client):
    client,db=finance_client
    run=PayrollRun(run_id="PR-TEST",period_start=date(2026,1,1),period_end=date(2026,1,31),pay_date=date(2026,2,1),
        employees_paid=1,total_gross=Decimal("100.00"),total_deductions=Decimal("0.00"),total_net=Decimal("100.00"),
        total_employer_contributions=Decimal("0.00"),total_employer_cost=Decimal("100.00"),status="APPROVED",calculation_version="test")
    item=PayrollItem(payroll_item_id="PI-TEST",run_id="PR-TEST",employee_id="E1",period_start=run.period_start,
        period_end=run.period_end,department_id="D1",role_id="R1",calendar_days=31,days_employed=31,
        lop_days=Decimal("0"),payable_days=Decimal("31"),monthly_fixed_gross=Decimal("100"),basic=Decimal("100"),
        hra=Decimal("0"),conveyance=Decimal("0"),medical=Decimal("0"),special_allowance=Decimal("0"),
        earned_fixed_pay=Decimal("100"),overtime_hours_paid=Decimal("0"),overtime_pay=Decimal("0"),variable_pay=Decimal("0"),
        gross_pay=Decimal("100"),pf_employee=Decimal("0"),esi_employee=Decimal("0"),professional_tax=Decimal("0"),
        tds=Decimal("0"),other_deductions=Decimal("0"),total_deductions=Decimal("0"),net_pay=Decimal("100"),
        pf_employer=Decimal("0"),esi_employer=Decimal("0"),employer_cost=Decimal("100"))
    db.add_all([run,item]);db.commit()
    first=client.post("/ledger/payroll-runs/PR-TEST/post",headers=hr())
    again=client.post("/ledger/payroll-runs/PR-TEST/post",headers=hr())
    assert first.status_code==201 and again.status_code==201
    assert first.json()["entry_id"]==again.json()["entry_id"]
    assert db.query(JournalEntry).filter_by(source_type="PAYROLL_RUN",source_id="PR-TEST").count()==1
    entry=db.get(JournalEntry,first.json()["entry_id"])
    assert entry.total_debit==entry.total_credit==Decimal("100.00")

def invoice_body(number="INV-TEST-1",gst="18"):
    return {"invoice_number":number,"client_id":"C1","invoice_date":date.today().isoformat(),
        "due_date":(date.today()+timedelta(days=30)).isoformat(),"currency":"INR","gst_rate_percent":gst,
        "items":[{"description":"Service","quantity":"2","unit_price":"100.00","revenue_account":"4001"}]}

def test_invoice_draft_edit_send_and_posted_immutability(finance_client):
    client,db=finance_client
    created=client.post("/invoices",json=invoice_body(),headers=hr())
    assert created.status_code==201 and created.json()["status"]=="DRAFT"
    inv=created.json();assert inv["subtotal"]=="200.00" and inv["gst_amount"]=="36.00" and inv["total_amount"]=="236.00"
    assert db.query(JournalEntry).count()==0
    updated=client.patch(f"/invoices/{inv['invoice_id']}",json={"items":[{"description":"Revised","quantity":"1","unit_price":"300.00","revenue_account":"4001"}]},headers=hr())
    assert updated.status_code==200 and updated.json()["total_amount"]=="354.00"
    sent=client.post(f"/invoices/{inv['invoice_id']}/send",headers=hr())
    assert sent.status_code==200 and sent.json()["status"]=="SENT" and sent.json()["ledger_entry_id"]
    sent_again=client.post(f"/invoices/{inv['invoice_id']}/send",headers=hr())
    assert sent_again.status_code==200 and sent_again.json()["ledger_entry_id"]==sent.json()["ledger_entry_id"]
    entry=db.get(JournalEntry,sent.json()["ledger_entry_id"])
    assert entry.total_debit==entry.total_credit==Decimal("354.00")
    lines=db.query(JournalLine).filter_by(entry_id=entry.entry_id).all()
    assert sum((line.debit for line in lines if line.account_code=="1100"),Decimal("0"))==Decimal("354.00")
    assert sum((line.credit for line in lines if line.account_code=="4001"),Decimal("0"))==Decimal("300.00")
    assert sum((line.credit for line in lines if line.account_code=="2200"),Decimal("0"))==Decimal("54.00")
    assert client.patch(f"/invoices/{inv['invoice_id']}",json={"po_number":"change"},headers=hr()).status_code==409

def test_supplied_tax_rates_and_draft_update_rollback(finance_client):
    client,db=finance_client
    unsupported=client.post("/invoices",json=invoice_body("INV-BAD-TAX","5"),headers=hr())
    assert unsupported.status_code==422
    inv=client.post("/invoices",json=invoice_body("INV-ROLLBACK","0"),headers=hr()).json()
    bad_update=client.patch(f"/invoices/{inv['invoice_id']}",json={"invoice_date":"2026-12-31"},headers=hr())
    assert bad_update.status_code==422
    db.expire_all()
    assert db.get(Invoice,inv["invoice_id"]).invoice_date==date.fromisoformat(inv["invoice_date"])

def test_invoice_payment_partial_idempotency_and_overpay(finance_client):
    client,db=finance_client
    inv=client.post("/invoices",json=invoice_body("INV-TEST-2","0"),headers=hr()).json()
    client.post(f"/invoices/{inv['invoice_id']}/send",headers=hr())
    body={"payment_date":date.today().isoformat(),"amount":"100.00","payment_mode":"NEFT","idempotency_key":"pay-key-0001"}
    first=client.post(f"/invoices/{inv['invoice_id']}/payments",json=body,headers=hr())
    again=client.post(f"/invoices/{inv['invoice_id']}/payments",json=body,headers=hr())
    assert first.status_code==201 and again.json()["payment_id"]==first.json()["payment_id"]
    changed_replay={**body,"payment_mode":"RTGS"}
    assert client.post(f"/invoices/{inv['invoice_id']}/payments",json=changed_replay,headers=hr()).status_code==409
    assert db.query(InvoicePayment).filter_by(invoice_id=inv["invoice_id"]).count()==1
    partial=client.get(f"/invoices/{inv['invoice_id']}",headers=hr()).json()
    assert partial["status"]=="PARTIALLY_PAID" and partial["balance_due"]=="100.00"
    body2={**body,"amount":"101.00","idempotency_key":"pay-key-0002"}
    assert client.post(f"/invoices/{inv['invoice_id']}/payments",json=body2,headers=hr()).status_code==422
    body3={**body,"amount":"100.00","idempotency_key":"pay-key-0003"}
    assert client.post(f"/invoices/{inv['invoice_id']}/payments",json=body3,headers=hr()).status_code==201
    assert client.get(f"/invoices/{inv['invoice_id']}",headers=hr()).json()["status"]=="PAID"

def test_cancel_draft_or_reverse_unpaid_posted_invoice(finance_client):
    client,db=finance_client
    draft=client.post("/invoices",json=invoice_body("INV-DRAFT","0"),headers=hr()).json()
    cancelled=client.post(f"/invoices/{draft['invoice_id']}/cancel",json={"reason":"Void draft"},headers=hr())
    assert cancelled.status_code==200 and cancelled.json()["status"]=="CANCELLED" and db.query(JournalEntry).count()==0
    assert client.post(f"/invoices/{draft['invoice_id']}/cancel",json={"reason":"Void draft"},headers=hr()).json()["status"]=="CANCELLED"
    assert client.post(f"/invoices/{draft['invoice_id']}/send",headers=hr()).status_code==409
    posted=client.post("/invoices",json=invoice_body("INV-POSTED","0"),headers=hr()).json()
    client.post(f"/invoices/{posted['invoice_id']}/send",headers=hr())
    cancelled=client.post(f"/invoices/{posted['invoice_id']}/cancel",json={"reason":"Customer cancelled"},headers=hr())
    assert cancelled.status_code==200 and cancelled.json()["status"]=="CANCELLED" and db.query(JournalEntry).count()==2
    again=client.post(f"/invoices/{posted['invoice_id']}/cancel",json={"reason":"Customer cancelled"},headers=hr())
    assert again.status_code==200 and again.json()["status"]=="CANCELLED" and db.query(JournalEntry).count()==2

def test_receivables_and_hr_authorization(finance_client):
    client,_=finance_client
    assert client.get("/clients").status_code==401
    inv=client.post("/invoices",json=invoice_body("INV-AR","0"),headers=hr()).json()
    client.post(f"/invoices/{inv['invoice_id']}/send",headers=hr())
    rows=client.get("/receivables",headers=hr()).json()
    assert rows==[{"client_id":"C1","client_name":"Test Client","outstanding_balance":"200.00"}]
