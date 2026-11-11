"""Idempotently import attendance and leave reference data in bounded batches.

Existing database records win on identifier conflicts, so reruns do not reset
leave decisions or balances changed by the API. Set ATTENDANCE_BATCH_SIZE to
change the attendance insert batch (default 5,000).
"""
import csv
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.config import settings
from app.database import SessionLocal, engine
from app.models import AttendanceRecord, Holiday, LeaveBalance, LeaveRequest, LeaveType

DATA = Path(settings.data_dir)
BATCH_SIZE = max(100, int(os.getenv("ATTENDANCE_BATCH_SIZE", "5000")))

def rows(filename):
    path = DATA / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required Phase 2 source CSV is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)

def conflict_safe_insert(db, model, batch):
    if not batch:
        return 0
    dialect = engine.dialect.name
    if dialect == "sqlite":
        # Use DBAPI executemany rather than expanded VALUES; this respects
        # SQLite's per-statement bind-variable limit and is faster for large files.
        stmt = sqlite_insert(model).on_conflict_do_nothing()
    elif dialect == "postgresql":
        stmt = pg_insert(model).on_conflict_do_nothing()
    else:
        raise RuntimeError(f"Idempotent batch loading is not configured for {dialect}")
    result = db.connection().execute(stmt, batch)
    return result.rowcount or 0

def load_reference(db):
    for row in rows("leave_types.csv"):
        conflict_safe_insert(db, LeaveType, [{
            "leave_type_code": row["leave_type_code"], "leave_type_name": row["leave_type_name"],
            "pay_type": row["pay_type"], "annual_quota_days": Decimal(row["annual_quota_days"]),
            "prorated_for_joiners": row["prorated_for_joiners"] == "Y",
            "carry_forward_allowed": row["carry_forward_allowed"] == "Y",
            "max_carry_forward_days": Decimal(row["max_carry_forward_days"] or "0"), "policy_note": row["policy_note"] or None,
        }])
    for row in rows("holidays.csv"):
        conflict_safe_insert(db, Holiday, [{
            "holiday_date": date.fromisoformat(row["holiday_date"]), "holiday_name": row["holiday_name"],
            "holiday_type": row["holiday_type"], "weekday": row["weekday"],
            "falls_on_weekend": row["falls_on_weekend"] == "Y", "calendar_note": row["calendar_note"] or None,
        }])

def load_balances(db):
    inserted = 0
    for row in rows("leave_balances.csv"):
        as_of = date.fromisoformat(row["as_of_date"])
        fy = row["financial_year"]
        values = []
        for code, ent, used, bal in [
            ("CL", "cl_entitlement", "cl_used", "cl_balance"),
            ("SL", "sl_entitlement", "sl_used", "sl_balance"),
            ("EL", None, "el_used_fy", "el_balance"),
        ]:
            used_d, bal_d = Decimal(row[used]), Decimal(row[bal])
            entitlement = Decimal(row[ent]) if ent else used_d + bal_d
            values.append({"balance_id": f"{row['employee_id']}:{code}:{fy}", "employee_id": row["employee_id"],
                "leave_type_code": code, "financial_year": fy, "as_of_date": as_of,
                "entitlement_days": entitlement, "used_days": used_d, "balance_days": bal_d, "version": 0})
        inserted += conflict_safe_insert(db, LeaveBalance, values)
    return inserted

def load_attendance(db):
    batch, inserted, seen = [], 0, 0
    for row in rows("attendance.csv"):
        def parse_time(value):
            if not value: return None
            parts = value.split(":")
            if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
                raise ValueError(f"Invalid time format in attendance row {row['attendance_id']}")
            if not 0 <= int(parts[1]) < 60 or (len(parts) == 3 and not 0 <= int(parts[2]) < 60):
                raise ValueError(f"Invalid time value in attendance row {row['attendance_id']}")
            return value
        batch.append({"attendance_id": row["attendance_id"], "employee_id": row["employee_id"],
            "attendance_date": date.fromisoformat(row["attendance_date"]), "weekday": row["weekday"],
            "status": row["status"], "leave_type_code": row["leave_type_code"] or None,
            "check_in": parse_time(row["check_in"]), "check_out": parse_time(row["check_out"]),
            "hours_worked": Decimal(row["hours_worked"]) if row["hours_worked"] else None,
            "overtime_hours": Decimal(row["overtime_hours"]) if row["overtime_hours"] else None,
            "late_flag": row["late_flag"] or None, "source": row["source"] or None,
            "data_quality_flag": row["data_quality_flag"] or None, "department_id": row["department_id"] or None})
        seen += 1
        if len(batch) >= BATCH_SIZE:
            inserted += conflict_safe_insert(db, AttendanceRecord, batch); batch.clear()
    inserted += conflict_safe_insert(db, AttendanceRecord, batch)
    return seen, inserted

def load_requests(db):
    batch = []
    for row in rows("leave_requests.csv"):
        batch.append({"leave_request_id": row["leave_request_id"], "employee_id": row["employee_id"],
            "leave_type_code": row["leave_type_code"], "start_date": date.fromisoformat(row["start_date"]),
            "end_date": date.fromisoformat(row["end_date"]), "days": Decimal(row["days"]),
            "reason": row["reason"], "status": row["status"], "applied_on": date.fromisoformat(row["applied_on"]),
            "approver_id": row["approver_id"] or None,
            "decided_on": date.fromisoformat(row["decided_on"]) if row["decided_on"] else None, "is_half_day": False})
        if len(batch) >= BATCH_SIZE:
            conflict_safe_insert(db, LeaveRequest, batch); batch.clear()
    conflict_safe_insert(db, LeaveRequest, batch)

def main():
    with SessionLocal.begin() as db:
        load_reference(db)
        balances = load_balances(db)
        attendance_count, inserted = load_attendance(db)
        load_requests(db)
    print(f"Task 6 import complete: attendance rows read={attendance_count}, newly inserted={inserted}, "
          f"attendance batch={BATCH_SIZE}; leave balance rows newly inserted={balances}; existing IDs preserved.")

if __name__ == "__main__":
    main()
