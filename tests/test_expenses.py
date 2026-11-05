from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import ChartOfAccount, Department, ExpenseBill, JournalEntry, JournalLine, Vendor
from tests.test_attendance_leave import token
from tests.auth_support import seed_test_users


@pytest.fixture
def expense_client(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-only-signing-secret-at-least-32-bytes")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory.begin() as db:
        db.add(Department(department_id="D1", department_name="Finance test", cost_center="CC1"))
        for code, name, typ, normal in [
            ("1001", "Bank - Test", "ASSET", "DEBIT"), ("1200", "GST Input Credit", "ASSET", "DEBIT"),
            ("2001", "Accounts Payable", "LIABILITY", "CREDIT"), ("5101", "Office Rent", "EXPENSE", "DEBIT")]:
            db.add(ChartOfAccount(account_code=code, account_name=name, account_type=typ,
                normal_balance=normal, parent_code=None, is_group=False, statement="Test", is_active=True))
        db.add(Vendor(vendor_id="V1", vendor_name="Test vendor", primary_expense_account="5101",
            payment_terms_days=30, city=None, gst_registration=None, is_active=True))
        seed_test_users(db, {"HR-CREATOR": "HR", "HR-OTHER": "Admin", "HR-APPROVER": "HR",
                             "HR-PAYER": "Admin"})
    session = factory()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _auth(actor="HR-CREATOR", role="hr"):
    return {"Authorization": f"Bearer {token(actor, role)}"}


def _bill(reference="INV-1", amount="100.00"):
    return {"vendor_id": "V1", "expense_date": "2026-04-01", "due_date": "2026-04-30",
        "bill_reference": reference, "description": "Monthly office rent", "category_account": "5101",
        "department_id": "D1", "amount_excl_gst": amount, "gst_rate_percent": "18"}


def test_bill_approval_separation_payment_and_no_expense_duplication(expense_client):
    client, db = expense_client
    created = client.post("/expenses", json=_bill(), headers=_auth())
    assert created.status_code == 201
    bill = created.json()
    expense_id = bill["expense_id"]
    assert bill["status"] == "SUBMITTED" and bill["gst_amount"] == 18

    payment_body = {"payment_date": "2026-04-10", "payment_mode": "NEFT", "cash_account_code": "1001",
                    "idempotency_key": "expense-payment-key-1"}
    assert client.post(f"/expenses/{expense_id}/payments", json=payment_body, headers=_auth("HR-OTHER")).status_code == 409
    assert client.post(f"/expenses/{expense_id}/approve", headers=_auth()).status_code == 403
    assert db.query(JournalEntry).count() == 0

    approved = client.post(f"/expenses/{expense_id}/approve", headers=_auth("HR-APPROVER"))
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    assert approved.json()["approved_by"] == "HR-APPROVER"
    assert [row["action"] for row in approved.json()["approval_history"]] == ["SUBMITTED", "APPROVED"]
    bill_entry = db.query(JournalEntry).filter_by(source_type="EXPENSE", source_id=expense_id).one()
    bill_lines = {line.account_code: (Decimal(line.debit), Decimal(line.credit))
                  for line in db.query(JournalLine).filter_by(entry_id=bill_entry.entry_id).all()}
    assert bill_lines == {"5101": (Decimal("100.00"), Decimal("0.00")),
                          "1200": (Decimal("18.00"), Decimal("0.00")),
                          "2001": (Decimal("0.00"), Decimal("118.00"))}
    assert bill_entry.total_debit == bill_entry.total_credit == Decimal("118.00")

    paid = client.post(f"/expenses/{expense_id}/payments", json=payment_body, headers=_auth("HR-PAYER"))
    assert paid.status_code == 201 and paid.json()["amount"] == 118
    assert client.get(f"/expenses/{expense_id}", headers=_auth()).json()["status"] == "PAID"
    payment_entry = db.get(JournalEntry, paid.json()["ledger_entry_id"])
    payment_lines = {line.account_code: (Decimal(line.debit), Decimal(line.credit))
                     for line in db.query(JournalLine).filter_by(entry_id=payment_entry.entry_id).all()}
    assert payment_lines == {"2001": (Decimal("118.00"), Decimal("0.00")),
                             "1001": (Decimal("0.00"), Decimal("118.00"))}
    assert payment_entry.total_debit == payment_entry.total_credit == Decimal("118.00")
    # Replayed payment returns the same ledger entry and does not add expense or payment postings.
    replay = client.post(f"/expenses/{expense_id}/payments", json=payment_body, headers=_auth("HR-PAYER"))
    assert replay.status_code == 201 and replay.json()["ledger_entry_id"] == payment_entry.entry_id
    assert db.query(JournalEntry).count() == 2
    assert sum((Decimal(line.debit) for line in db.query(JournalLine).filter_by(account_code="5101")), Decimal(0)) == Decimal("100.00")


def test_duplicate_detection_blocks_exact_and_warns_likely_matches(expense_client):
    client, _ = expense_client
    first = client.post("/expenses", json=_bill(), headers=_auth())
    assert first.status_code == 201
    exact = client.post("/expenses/duplicate-check", json={"vendor_id": "V1", "bill_reference": "INV-1",
        "expense_date": "2026-04-01", "total_amount": "118.00"}, headers=_auth()).json()
    assert len(exact["exact_duplicates"]) == 1
    assert client.post("/expenses", json=_bill(), headers=_auth()).status_code == 409
    likely = client.post("/expenses/duplicate-check", json={"vendor_id": "V1", "bill_reference": "INV-OTHER",
        "expense_date": "2026-04-01", "total_amount": "118.00"}, headers=_auth()).json()
    assert likely["exact_duplicates"] == [] and len(likely["likely_duplicates"]) == 1
    warning_bill = client.post("/expenses", json=_bill("INV-OTHER"), headers=_auth())
    assert warning_bill.status_code == 201 and len(warning_bill.json()["duplicate_warnings"]) == 1


def test_vendor_search_active_filter_reports_and_protected_routes(expense_client):
    client, db = expense_client
    assert client.get("/vendors").status_code == 401
    assert len(client.get("/vendors?search=test&active_only=true", headers=_auth()).json()) == 1
    db.add(Vendor(vendor_id="V2", vendor_name="Inactive supplier", primary_expense_account="5101",
        payment_terms_days=10, city=None, gst_registration=None, is_active=False)); db.commit()
    assert len(client.get("/vendors?active_only=false", headers=_auth()).json()) == 1
    created = client.post("/expenses", json=_bill(), headers=_auth()).json()
    client.post(f"/expenses/{created['expense_id']}/approve", headers=_auth("HR-APPROVER"))
    monthly = client.get("/expenses/reports/monthly?start_date=2026-04-01&end_date=2026-04-30",
                         headers=_auth()).json()
    assert monthly["months"][0]["amount_excl_gst"] == 100
    assert monthly["months"][0]["gst_amount"] == 18
    assert monthly["months"][0]["total_amount"] == 118
    assert len(client.get("/expenses/reports/vendor-wise", headers=_auth()).json()) == 1
    assert len(client.get("/expenses/reports/outstanding", headers=_auth()).json()) == 1
    assert client.get("/expenses/reports/paid-unpaid", headers=_auth()).json()["approved"]["total_amount"] == 118


def test_create_bill_validates_accounts_vendor_and_amounts(expense_client):
    client, _ = expense_client
    assert client.post("/expenses", json={**_bill(), "vendor_id": "NOPE"}, headers=_auth()).status_code == 422
    assert client.post("/expenses", json={**_bill(), "category_account": "2001"}, headers=_auth()).status_code == 422
