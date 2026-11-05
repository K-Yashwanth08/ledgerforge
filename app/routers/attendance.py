from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..attendance_service import get_monthly_summary
from ..database import get_db
from ..models import AttendanceRecord, Employee
from ..schemas import AttendanceOut, AttendanceSummaryOut
from ..security import current_actor, require_employee_access

router = APIRouter(prefix="/attendance", tags=["attendance"])

@router.get("", response_model=list[AttendanceOut])
def list_attendance(start_date: date | None = None, end_date: date | None = None,
                    employee_id: str | None = None, department_id: str | None = None,
                    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    if actor["role"] == "Employee":
        if employee_id and employee_id != actor["employee_id"]:
            require_employee_access(employee_id, actor)
        employee_id = actor["employee_id"]
        if not employee_id:
            raise HTTPException(403, "Employee account is not linked to an employee record")
    if employee_id and not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    q = db.query(AttendanceRecord)
    if start_date: q = q.filter(AttendanceRecord.attendance_date >= start_date)
    if end_date: q = q.filter(AttendanceRecord.attendance_date <= end_date)
    if employee_id: q = q.filter(AttendanceRecord.employee_id == employee_id)
    if department_id: q = q.filter(AttendanceRecord.department_id == department_id)
    return q.order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.employee_id).offset(offset).limit(limit).all()

@router.get("/summary/{employee_id}", response_model=AttendanceSummaryOut)
def attendance_summary(employee_id: str, month: str = Query(pattern=r"^\d{4}-\d{2}$"),
                       db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    require_employee_access(employee_id, actor)
    return get_monthly_summary(db, employee_id, month)
