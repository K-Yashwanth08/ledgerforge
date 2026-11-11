"""Salary history operations use inclusive effective dates and Decimal amounts."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .models import Employee, Role, SalaryComponent, SalaryRevision, SalaryStructure

CENT = Decimal("0.01")

def _annual_fixed(rows: list[SalaryStructure]) -> Decimal:
    monthly=sum((r.monthly_amount for r in rows if r.component.component_type == "EARNING" and r.component.is_fixed), Decimal("0.00"))
    return (monthly * Decimal("12")).quantize(CENT, rounding=ROUND_HALF_UP)

def _rows_for_date(db: Session, employee_id: str, effective_date: date):
    return (db.query(SalaryStructure)
        .filter(SalaryStructure.employee_id == employee_id, SalaryStructure.is_active.is_(True),
                SalaryStructure.effective_from <= effective_date,
                or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= effective_date))
        .order_by(SalaryStructure.component_id).all())

def get_structure(db: Session, employee_id: str, effective_date: date) -> dict:
    if not db.get(Employee, employee_id): raise LookupError(f"Employee {employee_id} was not found")
    rows=_rows_for_date(db, employee_id, effective_date)
    if not rows: raise LookupError(f"No salary structure exists for employee {employee_id} on {effective_date}")
    components=[{"component_id":r.component_id,"component_name":r.component_name,"component_type":r.component_type,
                 "taxable":r.component.taxable,"is_fixed":r.component.is_fixed,"monthly_amount":r.monthly_amount} for r in rows]
    return {"employee_id":employee_id,"effective_date":effective_date,"annual_fixed":_annual_fixed(rows),"components":components}

def get_revision_history(db: Session, employee_id: str) -> list[SalaryRevision]:
    if not db.get(Employee, employee_id): raise LookupError(f"Employee {employee_id} was not found")
    return (db.query(SalaryRevision).filter_by(employee_id=employee_id)
            .order_by(SalaryRevision.effective_from, SalaryRevision.revision_id).all())

def revise_salary(db: Session, employee_id: str, effective_date: date, new_structure: list, reason: str,
                  role_id_after: str | None = None, approved_by: str | None = None) -> SalaryRevision:
    employee=db.query(Employee).filter_by(employee_id=employee_id).with_for_update().one_or_none()
    if not employee: raise LookupError(f"Employee {employee_id} was not found")
    if db.query(SalaryRevision).filter_by(employee_id=employee_id,effective_from=effective_date).first():
        raise ValueError("A salary revision already exists for this employee on that date")
    role_id=role_id_after or employee.role_id
    if not db.get(Role, role_id): raise ValueError(f"Unknown role_id_after: {role_id}")
    component_ids=[x.component_id for x in new_structure]
    if not component_ids or len(set(component_ids)) != len(component_ids): raise ValueError("Salary components must be non-empty and unique")
    components={c.component_id:c for c in db.query(SalaryComponent).filter(SalaryComponent.component_id.in_(component_ids)).all()}
    missing=set(component_ids)-set(components)
    if missing: raise ValueError(f"Unknown salary component IDs: {', '.join(sorted(missing))}")
    amounts={x.component_id:x.monthly_amount for x in new_structure}
    if any(amount < 0 for amount in amounts.values()): raise ValueError("Salary amounts cannot be negative")

    current=db.query(SalaryStructure).filter(SalaryStructure.employee_id==employee_id,SalaryStructure.is_active.is_(True)).all()
    later=[r for r in current if r.effective_from >= effective_date]
    if later: raise ValueError("A revision cannot precede an existing active salary period")
    previous_rows=_rows_for_date(db,employee_id,effective_date - timedelta(days=1))
    previous=_annual_fixed(previous_rows) if previous_rows else None
    new_monthly=sum((amounts[cid] for cid in component_ids if components[cid].component_type=="EARNING" and components[cid].is_fixed),Decimal("0.00"))
    new_annual=(new_monthly*Decimal("12")).quantize(CENT,rounding=ROUND_HALF_UP)
    pct=((new_annual-previous)*Decimal("100")/previous).quantize(CENT,rounding=ROUND_HALF_UP) if previous else None
    revision_id=f"USR-{uuid4().hex[:12]}"
    revision=SalaryRevision(revision_id=revision_id,employee_id=employee_id,effective_from=effective_date,
        revision_reason=reason,previous_annual_fixed=previous,new_annual_fixed=new_annual,pct_change=pct,
        role_id_after=role_id,approved_by=approved_by,created_at=date.today())
    try:
        # Inclusive end dates: the old period runs through the day before the raise.
        for row in current:
            if row.effective_from < effective_date and (row.effective_to is None or row.effective_to >= effective_date):
                row.effective_to=effective_date-timedelta(days=1)
        db.add(revision); db.flush()
        db.add_all([SalaryStructure(structure_id=f"UST-{uuid4().hex[:12]}",employee_id=employee_id,
            component_id=cid,component_name=components[cid].component_name,component_type=components[cid].component_type,
            monthly_amount=amounts[cid],effective_from=effective_date,effective_to=None,revision_id=revision_id,is_active=True)
            for cid in component_ids])
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(revision)
    return revision
