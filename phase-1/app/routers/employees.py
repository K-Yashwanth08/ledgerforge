from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Department, Employee, Role
from ..schemas import EmployeeCreate, EmployeeOut, EmployeePatch

router = APIRouter(prefix="/employees", tags=["employees"])

def output(e: Employee):
    return {"employee_id":e.employee_id,"first_name":e.first_name,"last_name":e.last_name,"full_name":e.full_name,"work_email":e.work_email,"hire_date":e.hire_date,"exit_date":e.exit_date,"employment_status":e.employment_status,"employment_type":e.employment_type,"department_id":e.department_id,"department_name":e.department.department_name if e.department else None,"role_id":e.role_id,"role_title":e.role.role_title if e.role else None,"manager_id":e.manager_id,"work_location":e.work_location,"work_mode":e.work_mode}

def validate_refs(db: Session, department_id: str, role_id: str, manager_id: str | None, employee_id: str | None = None):
    if not db.get(Department, department_id): raise HTTPException(422, "Unknown department_id")
    role = db.get(Role, role_id)
    if not role or role.department_id != department_id: raise HTTPException(422, "role_id must exist in the selected department")
    if manager_id:
        if manager_id == employee_id: raise HTTPException(422, "An employee cannot manage themselves")
        if not db.get(Employee, manager_id): raise HTTPException(422, "Unknown manager_id")

@router.get("", response_model=list[EmployeeOut])
def list_employees(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), search: str | None = None, department_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Employee).filter(Employee.exit_date.is_(None))
    if search: q = q.filter(or_(Employee.full_name.ilike(f"%{search}%"), Employee.work_email.ilike(f"%{search}%"), Employee.employee_id.ilike(f"%{search}%")))
    if department_id: q = q.filter(Employee.department_id == department_id)
    return [output(e) for e in q.order_by(Employee.employee_id).offset(offset).limit(limit).all()]

@router.get("/stats", include_in_schema=True)
def employee_stats(db: Session = Depends(get_db)):
    active = db.query(func.count(Employee.employee_id)).filter(Employee.exit_date.is_(None)).scalar() or 0
    return {"active_employees": active}

@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, "Employee not found")
    return output(e)

@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    if db.get(Employee, payload.employee_id): raise HTTPException(409, "employee_id already exists")
    validate_refs(db, payload.department_id, payload.role_id, payload.manager_id, payload.employee_id)
    e = Employee(**payload.model_dump()); db.add(e)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Employee conflicts with existing data")
    db.refresh(e); return output(e)

@router.patch("/{employee_id}", response_model=EmployeeOut)
def patch_employee(employee_id: str, payload: EmployeePatch, db: Session = Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, "Employee not found")
    changes = payload.model_dump(exclude_unset=True)
    dept, role, mgr = changes.get("department_id", e.department_id), changes.get("role_id", e.role_id), changes.get("manager_id", e.manager_id)
    validate_refs(db, dept, role, mgr, employee_id)
    if mgr:
        ancestor = db.get(Employee, mgr); seen = {employee_id}
        while ancestor:
            if ancestor.employee_id in seen: raise HTTPException(422, "Manager change would create a reporting cycle")
            seen.add(ancestor.employee_id); ancestor = db.get(Employee, ancestor.manager_id) if ancestor.manager_id else None
    for key, value in changes.items(): setattr(e, key, value)
    if changes.get("employment_status") in {"Contract Ended", "Resigned", "Terminated"} and e.exit_date is None:
        e.exit_date = date.today()
    db.commit(); db.refresh(e); return output(e)

@router.delete("/{employee_id}", status_code=204)
def soft_delete(employee_id: str, db: Session = Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, "Employee not found")
    e.exit_date = date.today(); e.employment_status = "Resigned"; db.commit()
    return None

@router.get("/{employee_id}/team", response_model=list[EmployeeOut])
def team(employee_id: str, db: Session = Depends(get_db)):
    if not db.get(Employee, employee_id): raise HTTPException(404, "Employee not found")
    return [output(e) for e in db.query(Employee).filter(Employee.manager_id == employee_id, Employee.exit_date.is_(None)).order_by(Employee.employee_id).all()]
