from datetime import date, datetime, timezone
from calendar import monthrange
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from ..database import get_db
from ..ledger_service import post_payroll_run
from ..models import PayrollItem, PayrollRun
from ..payroll_service import calculate_employee_month, record_payroll_payment, reverse_payroll_run, run_payroll_month
from ..schemas import (PayrollItemOut, PayrollPaymentCreate, PayrollRunCreate,
                       PayrollRunDraftCreate, PayrollRunOut, ReversalCreate)
from ..security import (admin_actor, current_actor, hr_actor, require_employee_access,
                        require_linked_admin_for_employee_payroll)

router = APIRouter(prefix="/payroll", tags=["payroll"])

class PayrollBatchRequest(BaseModel):
    start_month: str = Field(pattern=r"^\d{4}-\d{2}$")

    @field_validator("start_month")
    @classmethod
    def valid_month(cls, value: str) -> str:
        year, month = map(int, value.split("-"))
        if not 1 <= month <= 12:
            raise ValueError("start_month must be a valid YYYY-MM month")
        return value


@router.post("/jobs/18-month", status_code=202)
def enqueue_18_month_payroll(payload: PayrollBatchRequest, _actor: dict = Depends(hr_actor)):
    from ..jobs import run_18_month_payroll
    result = run_18_month_payroll.delay(payload.start_month)
    return {"job_id": result.id, "status": "PENDING", "status_url": f"/api/v1/payroll/jobs/{result.id}"}


@router.get("/jobs/{job_id}")
def payroll_job_status(job_id: str, _actor: dict = Depends(hr_actor)):
    from ..jobs import celery_app
    result = celery_app.AsyncResult(job_id)
    meta = result.info if isinstance(result.info, dict) else {}
    response = {"job_id": job_id, "status": result.state,
                "current": meta.get("current", 0), "total": meta.get("total", 18),
                "month": meta.get("month"), "run_ids": meta.get("run_ids", [])}
    if result.failed():
        response["error"] = "Payroll batch failed; inspect worker logs for details."
    return response

def _run_out(run, warnings=None):
    value={name:getattr(run,name) for name in ("run_id","period_start","period_end","pay_date","employees_paid",
        "total_gross","total_deductions","total_net","total_employer_contributions","total_employer_cost","status",
        "approved_by","approved_at","journal_entry_id","payment_journal_entry_id","reversal_entry_id",
        "payment_reversal_entry_id","calculation_version")}
    value["warnings"] = warnings or []
    return value

@router.get("/calculate/{employee_id}")
def calculate_employee(employee_id: str, month: str = Query(pattern=r"^\d{4}-\d{2}$"),
                       db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    require_linked_admin_for_employee_payroll(actor)
    require_employee_access(employee_id, actor)
    return calculate_employee_month(db, employee_id, month)

@router.post("/runs", response_model=PayrollRunOut, status_code=201)
def create_run(payload: PayrollRunCreate, db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    actor = _actor
    run, warnings = run_payroll_month(db, payload.month, payload.pay_date, run_by=actor["sub"])
    return _run_out(run, warnings)

@router.post("/runs/draft", response_model=PayrollRunOut, status_code=201)
def create_draft(payload: PayrollRunDraftCreate, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    year, month = map(int, payload.month.split("-"))
    try: period_start = date(year, month, 1)
    except ValueError as exc: raise HTTPException(422, "month must be a valid YYYY-MM month") from exc
    period_end = date(year, month, monthrange(year, month)[1])
    key = f"draft:{payload.idempotency_key}"
    existing = db.query(PayrollRun).filter_by(idempotency_key=key).first()
    if existing:
        if existing.period_start != period_start: raise HTTPException(409, "Draft idempotency key belongs to another period")
        return _run_out(existing, ["Existing draft returned; no duplicate was created."])
    run = PayrollRun(run_id=f"LF-DRAFT-{period_start:%Y%m}-{uuid4().hex[:10].upper()}",
        period_start=period_start, period_end=period_end, pay_date=payload.pay_date, employees_paid=0,
        total_gross=Decimal("0.00"), total_deductions=Decimal("0.00"), total_net=Decimal("0.00"),
        total_employer_contributions=Decimal("0.00"), total_employer_cost=Decimal("0.00"),
        status="DRAFT", run_by=actor["sub"], approved_by=None,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None), approved_at=None,
        idempotency_key=key, journal_entry_id=None, payment_journal_entry_id=None,
        reversal_entry_id=None, payment_reversal_entry_id=None, calculation_version="pending")
    if db.query(PayrollRun).filter(PayrollRun.period_start == period_start).first():
        raise HTTPException(409, "A payroll run already exists for this period")
    db.add(run)
    try: db.commit(); db.refresh(run); return _run_out(run)
    except Exception: db.rollback(); raise

@router.post("/runs/{run_id}/process", response_model=PayrollRunOut)
def process_draft(run_id: str, db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    run = db.get(PayrollRun, run_id)
    if not run: raise HTTPException(404, "Payroll run not found")
    if run.status in {"PROCESSED", "APPROVED", "PAID", "REVERSED"}:
        return _run_out(run, ["Existing payroll run returned; no recalculation was performed."])
    if run.status != "DRAFT": raise HTTPException(409, "Only a draft payroll run can be processed")
    month = run.period_start.strftime("%Y-%m")
    result, warnings = run_payroll_month(db, month, run.pay_date, draft_run_id=run.run_id, run_by=actor["sub"])
    return _run_out(result, warnings)

@router.post("/runs/{run_id}/approve", response_model=PayrollRunOut)
def approve_run(run_id: str, db: Session = Depends(get_db), actor: dict = Depends(admin_actor)):
    run = db.get(PayrollRun, run_id)
    if not run: raise HTTPException(404, "Payroll run not found")
    if run.status == "APPROVED" and run.journal_entry_id:
        return _run_out(run, ["Payroll run is already approved and linked to its journal entry."])
    if run.status != "PROCESSED": raise HTTPException(409, "Only a processed payroll run can be approved")
    try:
        entry = post_payroll_run(db, run_id, actor["sub"])
        run.journal_entry_id = entry.entry_id
        run.approved_by = actor["sub"]
        run.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.status = "APPROVED"
        db.commit(); db.refresh(run)
        return _run_out(run)
    except Exception: db.rollback(); raise

@router.post("/runs/{run_id}/payments", status_code=201)
def pay_run(run_id: str, payload: PayrollPaymentCreate, db: Session = Depends(get_db), actor: dict = Depends(admin_actor)):
    run = db.get(PayrollRun, run_id)
    if not run: raise HTTPException(404, "Payroll run not found")
    try:
        payment = record_payroll_payment(db, run, payload, actor["sub"])
        db.commit(); db.refresh(payment)
        return {key: getattr(payment, key) for key in ("payment_id", "run_id", "payment_date", "amount",
            "bank_account_code", "payment_mode", "reference_no", "ledger_entry_id", "idempotency_key")}
    except Exception: db.rollback(); raise

@router.post("/runs/{run_id}/reverse", response_model=PayrollRunOut)
def reverse_run(run_id: str, payload: ReversalCreate, db: Session = Depends(get_db), actor: dict = Depends(admin_actor)):
    run = db.get(PayrollRun, run_id)
    if not run: raise HTTPException(404, "Payroll run not found")
    try:
        reversal = reverse_payroll_run(db, run, payload.entry_date, payload.reason, actor["sub"])
        db.commit(); db.refresh(run)
        return _run_out(run, [f"Payroll journal reversed by {reversal.entry_id}."])
    except Exception: db.rollback(); raise

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
    require_linked_admin_for_employee_payroll(actor)
    if not db.get(PayrollRun,run_id): raise HTTPException(404,"Payroll run not found")
    if actor["role"] == "Employee":
        if employee_id and employee_id != actor["employee_id"]:
            require_employee_access(employee_id, actor)
        employee_id=actor["employee_id"]
        if not employee_id: raise HTTPException(403, "Employee account is not linked to an employee record")
    q=db.query(PayrollItem).filter_by(run_id=run_id)
    if employee_id:q=q.filter_by(employee_id=employee_id)
    return q.order_by(PayrollItem.employee_id).offset(offset).limit(limit).all()
