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
from app.models import ChartOfAccount, JournalEntry, JournalLine
from tests.test_attendance_leave import token
from tests.auth_support import seed_test_users


@pytest.fixture
def report_client(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-only-signing-secret-at-least-32-bytes")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    accounts = [
        ("1000", "Assets", "ASSET", "DEBIT", None, True),
        ("1001", "Bank", "ASSET", "DEBIT", "1000", False),
        ("2000", "Liabilities", "LIABILITY", "CREDIT", None, True),
        ("2001", "Payables", "LIABILITY", "CREDIT", "2000", False),
        ("3000", "Equity", "EQUITY", "CREDIT", None, True),
        ("3001", "Capital", "EQUITY", "CREDIT", "3000", False),
        ("4000", "Income", "INCOME", "CREDIT", None, True),
        ("4001", "Revenue", "INCOME", "CREDIT", "4000", False),
        ("5000", "Expenses", "EXPENSE", "DEBIT", None, True),
        ("5001", "Operating expense", "EXPENSE", "DEBIT", "5000", False),
    ]
    with factory.begin() as db:
        db.add_all([ChartOfAccount(account_code=code, account_name=name, account_type=kind,
            normal_balance=normal, parent_code=parent, is_group=group,
            statement="Balance Sheet" if kind in {"ASSET", "LIABILITY", "EQUITY"} else "Profit & Loss",
            is_active=True) for code, name, kind, normal, parent, group in accounts])
        _entry(db, "JE-OPEN", date(2026, 4, 1), [("1001", "1000", "0"), ("3001", "0", "1000")])
        _entry(db, "JE-REVENUE", date(2026, 4, 15), [("1001", "500", "0"), ("4001", "0", "500")])
        _entry(db, "JE-EXPENSE", date(2026, 4, 20), [("5001", "200", "0"), ("2001", "0", "200")])
        seed_test_users(db, {"REPORTER": "HR"})
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


def _entry(db, entry_id, entry_date, lines):
    debit = sum((Decimal(dr) for _, dr, _ in lines), Decimal("0"))
    credit = sum((Decimal(cr) for _, _, cr in lines), Decimal("0"))
    db.add(JournalEntry(entry_id=entry_id, entry_date=entry_date,
        posting_period=entry_date.strftime("%Y-%m"), financial_year="FY2026-27",
        description=entry_id, source_type="TEST", source_id=None, status="POSTED",
        total_debit=debit, total_credit=credit))
    db.flush()
    db.add_all([JournalLine(line_id=f"{entry_id}-{index}", entry_id=entry_id, line_no=index,
        account_code=code, debit=Decimal(dr), credit=Decimal(cr), line_description=entry_id)
        for index, (code, dr, cr) in enumerate(lines, 1)])


def _hr():
    return {"Authorization": f"Bearer {token('REPORTER', 'hr')}"}


def _money(value):
    return Decimal(str(value))


def test_trial_balance_columns_balance_and_group_rollups(report_client):
    client, _ = report_client
    result = client.get("/reports/trial-balance?start_date=2026-04-15&end_date=2026-04-30",
                        headers=_hr())
    assert result.status_code == 200
    body = result.json()
    assert body["balanced"] is True
    assert _money(body["totals"]["closing_debit"]) == _money(body["totals"]["closing_credit"]) == Decimal("1700.00")
    rows = {r["account_code"]: r for r in body["rows"]}
    assert rows["1000"]["is_group"] is True
    assert _money(rows["1000"]["closing_debit"]) == _money(rows["1001"]["closing_debit"]) == Decimal("1500.00")
    assert _money(rows["1001"]["opening_debit"]) == Decimal("1000.00")
    assert _money(rows["1001"]["period_debit"]) == Decimal("500.00")
    # Totals use posting accounts once, never group rows plus their children.
    assert sum(Decimal(r["closing_debit"]) for r in body["rows"] if not r["is_group"]) == Decimal("1700.00")


def test_profit_and_loss_groups_children_once_and_filters_dates(report_client):
    client, _ = report_client
    result = client.get("/reports/profit-and-loss?start_date=2026-04-15&end_date=2026-04-30",
                        headers=_hr())
    assert result.status_code == 200
    body = result.json()
    assert _money(body["total_revenue"]) == Decimal("500.00")
    assert _money(body["total_expenses"]) == Decimal("200.00")
    assert _money(body["net_profit"]) == Decimal("300.00")
    assert _money(body["revenue"][0]["amount"]) == Decimal("500.00")
    assert _money(body["revenue"][0]["accounts"][0]["amount"]) == Decimal("500.00")
    empty = client.get("/reports/profit-and-loss?start_date=2026-05-01&end_date=2026-05-31",
                       headers=_hr()).json()
    assert _money(empty["net_profit"]) == Decimal("0.00")
    assert client.get("/reports/profit-and-loss?start_date=2026-05-31&end_date=2026-05-01",
                      headers=_hr()).status_code == 422


def test_balance_sheet_equation_and_current_profit(report_client):
    client, _ = report_client
    result = client.get("/reports/balance-sheet?start_date=2026-04-15&end_date=2026-04-30",
                        headers=_hr())
    assert result.status_code == 200
    body = result.json()
    assert _money(body["assets_total"]) == Decimal("1500.00")
    assert _money(body["liabilities_total"]) == Decimal("200.00")
    assert _money(body["equity_total_including_prior_profit"]) == Decimal("1000.00")
    assert _money(body["current_period_profit"]) == Decimal("300.00")
    assert body["balanced"] is True and _money(body["difference"]) == Decimal("0.00")


def test_empty_period_trial_balance_retains_opening_and_csv_excludes_group_rows(report_client):
    client, _ = report_client
    body = client.get("/reports/trial-balance?start_date=2026-05-01&end_date=2026-05-31",
                      headers=_hr()).json()
    assert _money(body["totals"]["period_debit"]) == _money(body["totals"]["period_credit"]) == Decimal("0.00")
    assert _money(body["totals"]["closing_debit"]) == _money(body["totals"]["closing_credit"]) == Decimal("1700.00")
    response = client.get("/reports/trial-balance.csv?start_date=2026-04-15&end_date=2026-04-30",
                          headers=_hr())
    assert response.status_code == 200 and "text/csv" in response.headers["content-type"]
    assert "1000,Assets" not in response.text and "1001,Bank" in response.text


def test_reports_require_authorization_and_reject_unbalanced_posted_entry(report_client):
    client, db = report_client
    assert client.get("/reports/trial-balance").status_code == 401
    _entry(db, "JE-BAD", date(2026, 4, 25), [("1001", "100", "0"), ("4001", "0", "99")])
    db.commit()
    response = client.get("/reports/trial-balance?start_date=2026-04-01&end_date=2026-04-30",
                          headers=_hr())
    assert response.status_code == 409
    assert "JE-BAD" in response.json()["detail"]["entry_ids"]
