from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..attendance_service import apply_leave, decide_leave, list_balances
from ..database import get_db
from ..models import Holiday, LeaveRequest, LeaveType
from ..schemas import LeaveBalanceOut, LeaveRequestCreate, LeaveRequestOut, LeaveTypeOut
from ..security import current_actor, hr_actor

router = APIRouter(prefix="/leave", tags=["leave"])

@router.get("/holidays")
def holidays(start_date: date | None = None, end_date: date | None = None,
             db: Session = Depends(get_db), _actor: dict = Depends(current_actor)):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    q = db.query(Holiday)
    if start_date: q = q.filter(Holiday.holiday_date >= start_date)
    if end_date: q = q.filter(Holiday.holiday_date <= end_date)
    return q.order_by(Holiday.holiday_date).all()

def _owned_or_hr(employee_id: str, actor: dict) -> None:
    if actor["role"] not in {"hr", "admin"} and actor["sub"] != employee_id:
        raise HTTPException(403, "You may view only your own leave information")

@router.get("/types", response_model=list[LeaveTypeOut])
def leave_types(db: Session = Depends(get_db), _actor: dict = Depends(current_actor)):
    return db.query(LeaveType).order_by(LeaveType.leave_type_code).all()

@router.get("/balances/{employee_id}", response_model=list[LeaveBalanceOut])
def leave_balances(employee_id: str, db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    _owned_or_hr(employee_id, actor)
    return list_balances(db, employee_id)

@router.get("/requests", response_model=list[LeaveRequestOut])
def leave_requests(employee_id: str | None = None, status: str | None = None,
                   limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    if actor["role"] not in {"hr", "admin"}:
        employee_id = actor["sub"]
    q = db.query(LeaveRequest)
    if employee_id: q = q.filter(LeaveRequest.employee_id == employee_id)
    if status: q = q.filter(LeaveRequest.status.ilike(status))
    return q.order_by(LeaveRequest.applied_on.desc(), LeaveRequest.leave_request_id).offset(offset).limit(limit).all()

@router.post("/requests", response_model=LeaveRequestOut, status_code=201)
def create_leave(payload: LeaveRequestCreate, db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    return apply_leave(db, payload, actor["sub"])

@router.post("/requests/{request_id}/approve", response_model=LeaveRequestOut)
def approve_leave(request_id: str, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    return decide_leave(db, request_id, "approve", actor["sub"])

@router.post("/requests/{request_id}/reject", response_model=LeaveRequestOut)
def reject_leave(request_id: str, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    return decide_leave(db, request_id, "reject", actor["sub"])
