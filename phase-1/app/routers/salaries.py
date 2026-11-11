from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import SalaryRevisionCreate, SalaryRevisionOut, SalaryStructureOut
from ..salary_service import get_revision_history, get_structure, revise_salary

router=APIRouter(prefix="/employees",tags=["salaries"])

@router.get("/{employee_id}/salary",response_model=SalaryStructureOut)
def applicable_salary(employee_id: str, effective_date: date = Query(default_factory=date.today), db: Session = Depends(get_db)):
    try: return get_structure(db,employee_id,effective_date)
    except LookupError as exc: raise HTTPException(404,str(exc)) from exc

@router.get("/{employee_id}/salary/revisions",response_model=list[SalaryRevisionOut])
def salary_history(employee_id: str,db: Session=Depends(get_db)):
    try: return get_revision_history(db,employee_id)
    except LookupError as exc: raise HTTPException(404,str(exc)) from exc

@router.post("/{employee_id}/salary/revisions",response_model=SalaryRevisionOut,status_code=201)
def create_salary_revision(employee_id: str,payload: SalaryRevisionCreate,db: Session=Depends(get_db)):
    try:
        return revise_salary(db,employee_id,payload.effective_from,payload.components,payload.revision_reason,
                             payload.role_id_after,payload.approved_by)
    except LookupError as exc: raise HTTPException(404,str(exc)) from exc
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
