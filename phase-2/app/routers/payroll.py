from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import PayrollItem, PayrollRun
from ..payroll_service import calculate_employee_month, run_payroll_month
from ..schemas import PayrollItemOut, PayrollRunCreate, PayrollRunOut
from ..security import current_actor, hr_actor

router = APIRouter(prefix="/payroll", tags=["payroll"])

def _run_out(run, warnings=None):
    value={name:getattr(run,name) for name in ("run_id","period_start","period_end","pay_date","employees_paid",
        "total_gross","total_deductions","total_net","total_employer_contributions","total_employer_cost","status","calculation_version")}
    value["warnings"] = warnings or []
    return value

@router.get("/calculate/{employee_id}")
def calculate_employee(employee_id: str, month: str = Query(pattern=r"^\d{4}-\d{2}$"),
                       db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    if actor["role"] not in {"hr","admin"} and actor["sub"] != employee_id:
        raise HTTPException(403, "You may view only your own payroll calculation")
    return calculate_employee_month(db, employee_id, month)

@router.post("/runs", response_model=PayrollRunOut, status_code=201)
def create_run(payload: PayrollRunCreate, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    run, warnings = run_payroll_month(db, payload.month, payload.pay_date)
    return _run_out(run, warnings)

@router.get("/runs", response_model=list[PayrollRunOut])
def list_runs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    runs=db.query(PayrollRun).order_by(PayrollRun.period_start.desc(),PayrollRun.run_id).offset(offset).limit(limit).all()
    return [_run_out(r) for r in runs]

@router.get("/runs/{run_id}", response_model=PayrollRunOut)
def get_run(run_id: str, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    run=db.get(PayrollRun,run_id)
    if not run: raise HTTPException(404,"Payroll run not found")
    return _run_out(run)

@router.get("/runs/{run_id}/items", response_model=list[PayrollItemOut])
def list_run_items(run_id: str, employee_id: str | None = None,
                   limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    if not db.get(PayrollRun,run_id): raise HTTPException(404,"Payroll run not found")
    if actor["role"] not in {"hr","admin"}:
        if employee_id and employee_id != actor["sub"]: raise HTTPException(403,"You may view only your own payroll record")
        employee_id=actor["sub"]
    q=db.query(PayrollItem).filter_by(run_id=run_id)
    if employee_id:q=q.filter_by(employee_id=employee_id)
    return q.order_by(PayrollItem.employee_id).offset(offset).limit(limit).all()
