from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import and_, func, update
from sqlalchemy.orm import Session
from .models import AttendanceRecord, Employee, Holiday, LeaveBalance, LeaveRequest, LeaveType

ZERO = Decimal("0.00")

def get_monthly_summary(db: Session, employee_id: str, month: str) -> dict:
    try:
        year, mon = map(int, month.split("-"))
        first = date(year, mon, 1)
    except (ValueError, TypeError):
        raise HTTPException(422, "month must use YYYY-MM format")
    last = date(year, mon, monthrange(year, mon)[1])
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    rows = db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id,
        AttendanceRecord.attendance_date >= first, AttendanceRecord.attendance_date <= last).all()
    return {
        "employee_id": employee_id, "month": month,
        "days_present": sum(r.status == "PRESENT" for r in rows),
        "work_from_home_days": sum(r.status == "WFH" for r in rows),
        "absent_days": sum((Decimal("0.5") if r.status == "HALF_DAY_UNPAID" else Decimal("1"))
                           for r in rows if r.status in {"ABSENT_LOP", "HALF_DAY_UNPAID"}),
        "paid_leave_days": sum(r.status == "PAID_LEAVE" for r in rows),
        "unpaid_leave_days": sum(r.status == "UNPAID_LEAVE" for r in rows),
        "late_occurrences": sum((r.late_flag or "").upper() == "Y" for r in rows),
        "overtime_hours": sum((r.overtime_hours or ZERO for r in rows), ZERO),
        "missing_checkout_records": sum((r.data_quality_flag or "").upper() == "MISSING_CHECKOUT" for r in rows),
    }

def working_days(db: Session, start: date, end: date) -> Decimal:
    holiday_dates = {r[0] for r in db.query(Holiday.holiday_date).filter(Holiday.holiday_date.between(start, end)).all()}
    days = Decimal("0")
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holiday_dates:
            days += Decimal("1")
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return days

def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"FY{start}-{(start + 1) % 100:02d}"

def list_balances(db: Session, employee_id: str) -> list[LeaveBalance]:
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    return db.query(LeaveBalance).filter_by(employee_id=employee_id).order_by(LeaveBalance.leave_type_code).all()

def apply_leave(db: Session, payload, actor_sub: str) -> LeaveRequest:
    if payload.employee_id != actor_sub:
        raise HTTPException(403, "Employees may submit leave only for their own account")
    if payload.end_date < payload.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    if payload.start_date < date.today():
        raise HTTPException(422, "Leave requests cannot start in the past")
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.exit_date is not None:
        raise HTTPException(404, "Active employee not found")
    leave_type = db.get(LeaveType, payload.leave_type_code)
    if not leave_type:
        raise HTTPException(422, "Unknown leave_type_code")
    fy = financial_year(payload.start_date)
    if financial_year(payload.end_date) != fy:
        raise HTTPException(422, "A leave request cannot cross financial years")
    if payload.is_half_day:
        if payload.start_date != payload.end_date or payload.start_date.weekday() >= 5 or db.get(Holiday, payload.start_date):
            raise HTTPException(422, "Half-day leave must be on a single working day")
        days = Decimal("0.5")
    else:
        days = working_days(db, payload.start_date, payload.end_date)
    if days <= 0:
        raise HTTPException(422, "The requested dates contain no working days")
    overlap = db.query(LeaveRequest).filter(LeaveRequest.employee_id == payload.employee_id,
        LeaveRequest.status.in_(["Pending", "Approved"]), LeaveRequest.start_date <= payload.end_date,
        LeaveRequest.end_date >= payload.start_date).first()
    if overlap:
        raise HTTPException(409, f"Dates overlap leave request {overlap.leave_request_id}")
    balance = None
    if leave_type.pay_type.lower() != "unpaid":
        balance = db.query(LeaveBalance).filter_by(employee_id=payload.employee_id,
            leave_type_code=payload.leave_type_code, financial_year=fy).with_for_update().first()
        if balance is None:
            raise HTTPException(409, f"No configured {fy} leave balance exists for {payload.leave_type_code}")
        pending = db.query(func.coalesce(func.sum(LeaveRequest.days), 0)).filter(
            LeaveRequest.employee_id == payload.employee_id, LeaveRequest.leave_type_code == payload.leave_type_code,
            LeaveRequest.status == "Pending", LeaveRequest.start_date >= date(int(fy[2:6]), 4, 1),
            LeaveRequest.start_date <= date(int(fy[2:6]) + 1, 3, 31),
        ).scalar()
        if balance.balance_days - Decimal(str(pending or 0)) < days:
            raise HTTPException(422, "Insufficient available leave balance")
    req = LeaveRequest(leave_request_id=f"LR-{uuid4().hex[:16].upper()}", employee_id=payload.employee_id,
        leave_type_code=payload.leave_type_code, start_date=payload.start_date, end_date=payload.end_date,
        days=days, reason=payload.reason.strip(), status="Pending", applied_on=date.today(), is_half_day=payload.is_half_day)
    db.add(req)
    try:
        db.commit(); db.refresh(req)
    except Exception:
        db.rollback(); raise
    return req

def decide_leave(db: Session, request_id: str, decision: str, approver_id: str) -> LeaveRequest:
    try:
        req = db.query(LeaveRequest).filter_by(leave_request_id=request_id).with_for_update().first()
        if not req:
            raise HTTPException(404, "Leave request not found")
        if req.status != "Pending":
            raise HTTPException(409, f"Leave request is already {req.status.lower()}")
        if decision == "reject":
            result = db.execute(update(LeaveRequest).where(and_(LeaveRequest.leave_request_id == request_id,
                LeaveRequest.status == "Pending")).values(status="Rejected", approver_id=approver_id, decided_on=date.today()))
            if result.rowcount != 1:
                raise HTTPException(409, "Leave request was already decided")
        else:
            lt = db.get(LeaveType, req.leave_type_code)
            if lt.pay_type.lower() != "unpaid":
                fy = financial_year(req.start_date)
                bal = db.query(LeaveBalance).filter_by(employee_id=req.employee_id,
                    leave_type_code=req.leave_type_code, financial_year=fy).with_for_update().first()
                if bal is None:
                    raise HTTPException(409, "No configured leave balance exists for this request")
                result = db.execute(update(LeaveBalance).where(and_(LeaveBalance.balance_id == bal.balance_id,
                    LeaveBalance.version == bal.version, LeaveBalance.balance_days >= req.days)).values(
                    used_days=LeaveBalance.used_days + req.days, balance_days=LeaveBalance.balance_days - req.days,
                    version=LeaveBalance.version + 1))
                if result.rowcount != 1:
                    raise HTTPException(422, "Insufficient balance or a concurrent approval changed the balance")
            result = db.execute(update(LeaveRequest).where(and_(LeaveRequest.leave_request_id == request_id,
                LeaveRequest.status == "Pending")).values(status="Approved", approver_id=approver_id, decided_on=date.today()))
            if result.rowcount != 1:
                raise HTTPException(409, "Leave request was already decided")
        db.commit()
        db.refresh(req)
        return req
    except Exception:
        db.rollback()
        raise
