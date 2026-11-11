import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import AttendanceRecord, Department, Employee, Holiday, LeaveBalance, LeaveRequest, LeaveType, Role

def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")

def token(sub="E1", role="employee"):
    now = int(datetime.now(timezone.utc).timestamp())
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    claims = {"sub": sub, "role": role, "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
              "iat": now, "exp": now + 3600}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.secret_key.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"

@pytest.fixture
def ledger_client(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-only-signing-secret-at-least-32-bytes")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Factory.begin() as db:
        db.add(Department(department_id="D1", department_name="Test", cost_center="CC1"))
        db.add(Role(role_id="R1", department_id="D1", role_title="Test role", level=1, grade="L1",
                    band_min_annual=1, band_mid_annual=2, band_max_annual=3, overtime_eligible="N", band_year=2026))
        db.add(Employee(employee_id="E1", first_name="Test", last_name="Person", full_name="Test Person",
            work_email="e1@example.test", hire_date=date(2020, 1, 1), employment_status="Active",
            employment_type="Permanent", department_id="D1", role_id="R1"))
        db.add_all([LeaveType(leave_type_code="CL", leave_type_name="Casual leave", pay_type="Paid",
            annual_quota_days=Decimal("12"), prorated_for_joiners=True, carry_forward_allowed=False,
            max_carry_forward_days=Decimal("0")), LeaveType(leave_type_code="LOP", leave_type_name="Loss of pay",
            pay_type="Unpaid", annual_quota_days=Decimal("0"), prorated_for_joiners=False,
            carry_forward_allowed=False, max_carry_forward_days=Decimal("0"))])
        db.add(LeaveBalance(balance_id="E1:CL:FY2026-27", employee_id="E1", leave_type_code="CL",
            financial_year="FY2026-27", as_of_date=date.today(), entitlement_days=Decimal("5"),
            used_days=Decimal("0"), balance_days=Decimal("5"), version=0))
    session = Factory()
    def override(): yield session
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c: yield c, session
    app.dependency_overrides.clear(); session.close(); Base.metadata.drop_all(engine); engine.dispose()

def auth(sub="E1", role="employee"):
    return {"Authorization": f"Bearer {token(sub, role)}"}

def next_monday():
    d = date.today() + timedelta(days=(7 - date.today().weekday()) % 7)
    return d if d > date.today() else d + timedelta(days=7)

def request_body(start, end, **extra):
    return {"employee_id": "E1", "leave_type_code": "CL", "start_date": start.isoformat(),
            "end_date": end.isoformat(), "reason": "Planned leave", **extra}

def test_monthly_summary_and_missing_checkout_policy(ledger_client):
    client, db = ledger_client
    db.add_all([
        AttendanceRecord(attendance_id="A1", employee_id="E1", attendance_date=date(2025,4,1), weekday="Tue", status="PRESENT", check_in="09:00", check_out=None, hours_worked=Decimal("7.50"), overtime_hours=Decimal("1.25"), late_flag="Y", data_quality_flag="MISSING_CHECKOUT", department_id="D1"),
        AttendanceRecord(attendance_id="A2", employee_id="E1", attendance_date=date(2025,4,2), weekday="Wed", status="WFH", hours_worked=Decimal("8.00"), overtime_hours=Decimal("0"), late_flag="N", department_id="D1"),
        AttendanceRecord(attendance_id="A3", employee_id="E1", attendance_date=date(2025,4,3), weekday="Thu", status="ABSENT_LOP", department_id="D1"),
        AttendanceRecord(attendance_id="A4", employee_id="E1", attendance_date=date(2025,4,4), weekday="Fri", status="HALF_DAY_UNPAID", department_id="D1"),
    ]); db.commit()
    r = client.get("/attendance/summary/E1?month=2025-04", headers=auth(role="hr"))
    assert r.status_code == 200
    assert r.json() == {"employee_id":"E1","month":"2025-04","days_present":1,"work_from_home_days":1,
        "absent_days":"1.5","paid_leave_days":0,"unpaid_leave_days":0,"late_occurrences":1,
        "overtime_hours":"1.25","missing_checkout_records":1}
    assert db.get(AttendanceRecord,"A1").check_out is None and db.get(AttendanceRecord,"A1").hours_worked == Decimal("7.50")

def test_attendance_requires_hr_token(ledger_client):
    client, _ = ledger_client
    assert client.get("/attendance").status_code == 401
    assert client.get("/attendance", headers=auth()).status_code == 403
    assert client.get("/attendance", headers=auth(role="hr")).status_code == 200

def test_attendance_list_filters_source_records_and_rejects_unknown_employee(ledger_client):
    client, db = ledger_client
    db.add_all([
        AttendanceRecord(attendance_id="LIST-1", employee_id="E1", attendance_date=date(2025,4,1),
            weekday="Tue", status="PRESENT", hours_worked=Decimal("7.50"), overtime_hours=Decimal("1.25"),
            department_id="D1"),
        AttendanceRecord(attendance_id="LIST-2", employee_id="E1", attendance_date=date(2025,4,2),
            weekday="Wed", status="WFH", hours_worked=Decimal("8.00"), overtime_hours=Decimal("0"), department_id="D1"),
    ])
    db.commit()
    response = client.get("/attendance?employee_id=E1&start_date=2025-04-01&end_date=2025-04-01", headers=auth("HR1", "hr"))
    assert response.status_code == 200
    assert len(response.json()) == 1 and response.json()[0]["overtime_hours"] == "1.25"
    assert client.get("/attendance?employee_id=UNKNOWN", headers=auth("HR1", "hr")).status_code == 404
    assert client.get("/attendance?start_date=2025-04-02&end_date=2025-04-01", headers=auth("HR1", "hr")).status_code == 422

def test_leave_holidays_are_authenticated_and_date_filterable(ledger_client):
    client, db = ledger_client
    db.add_all([
        Holiday(holiday_date=date(2026,1,1), holiday_name="New Year", holiday_type="National", weekday="Thu", falls_on_weekend=False),
        Holiday(holiday_date=date(2026,8,15), holiday_name="Independence Day", holiday_type="National", weekday="Sat", falls_on_weekend=True),
    ])
    db.commit()
    assert client.get("/leave/holidays").status_code == 401
    rows = client.get("/leave/holidays?start_date=2026-01-01&end_date=2026-06-30", headers=auth()).json()
    assert [row["holiday_name"] for row in rows] == ["New Year"]
    assert client.get("/leave/holidays?start_date=2026-08-01&end_date=2026-01-01", headers=auth()).status_code == 422

def test_leave_excludes_weekends_and_holidays_and_half_day(ledger_client):
    client, db = ledger_client
    monday = next_monday(); tuesday = monday + timedelta(days=1); friday = monday + timedelta(days=4)
    db.add(Holiday(holiday_date=tuesday, holiday_name="Test holiday", holiday_type="National", weekday="Tue", falls_on_weekend=False)); db.commit()
    r = client.post("/leave/requests", json=request_body(monday, friday), headers=auth())
    assert r.status_code == 201 and r.json()["days"] == "4.00"
    following = monday + timedelta(days=7)
    h = client.post("/leave/requests", json=request_body(following, following, is_half_day=True), headers=auth())
    assert h.status_code == 201 and h.json()["days"] == "0.50"

def test_leave_insufficient_balance_invalid_dates_and_owner_access(ledger_client):
    client, db = ledger_client
    db.get(LeaveBalance, "E1:CL:FY2026-27").balance_days = Decimal("3")
    db.commit()
    monday = next_monday(); end = monday + timedelta(days=4)
    assert client.post("/leave/requests", json=request_body(monday, end), headers=auth()).status_code == 422
    assert client.post("/leave/requests", json=request_body(end, monday), headers=auth()).status_code == 422
    assert client.post("/leave/requests", json=request_body(monday, monday), headers=auth(sub="E2")).status_code == 403

def test_approval_deducts_once_and_rejection_does_not_deduct(ledger_client):
    client, db = ledger_client
    monday = next_monday(); approved = client.post("/leave/requests", json=request_body(monday, monday + timedelta(days=1)), headers=auth())
    assert approved.status_code == 201 and approved.json()["days"] == "2.00"
    request_id = approved.json()["leave_request_id"]
    decision = client.post(f"/leave/requests/{request_id}/approve", headers=auth("HR1","hr"))
    assert decision.status_code == 200 and decision.json()["status"] == "Approved"
    assert client.post(f"/leave/requests/{request_id}/approve", headers=auth("HR1","hr")).status_code == 409
    balance = db.get(LeaveBalance, "E1:CL:FY2026-27")
    assert balance.used_days == Decimal("2.00") and balance.balance_days == Decimal("3.00") and balance.version == 1
    other = client.post("/leave/requests", json=request_body(monday + timedelta(days=7), monday + timedelta(days=7)), headers=auth())
    assert other.status_code == 201
    rj = client.post(f"/leave/requests/{other.json()['leave_request_id']}/reject", headers=auth("HR1","hr"))
    assert rj.status_code == 200 and rj.json()["status"] == "Rejected"
    assert db.get(LeaveBalance, "E1:CL:FY2026-27").balance_days == Decimal("3.00")

def test_repeated_application_uses_leave_balance_snapshot_plus_pending(ledger_client):
    client, _ = ledger_client
    monday = next_monday()
    a = client.post("/leave/requests", json=request_body(monday, monday+timedelta(days=1)), headers=auth())
    b = client.post("/leave/requests", json=request_body(monday+timedelta(days=7), monday+timedelta(days=10)), headers=auth())
    assert a.status_code == 201 and b.status_code == 422
