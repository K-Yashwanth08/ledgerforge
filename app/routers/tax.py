"""Admin-managed effective-dated tax and statutory configuration."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import (EmployeeTaxAuditEvent, EmployeeTaxDeclaration, EmployeeTaxElection,
                      Employee, StatutoryRate, TaxParameter, TaxSlab)
from ..security import (admin_actor, current_actor, hr_actor, require_employee_access)

router = APIRouter(prefix="/tax", tags=["tax and statutory"])

class Slab(BaseModel):
    lower_limit: Decimal = Field(ge=0)
    upper_limit: Decimal | None = Field(default=None, gt=0)
    tax_rate: Decimal = Field(ge=0, le=100)

class SlabSet(BaseModel):
    financial_year: str = Field(pattern=r"^FY\d{4}-\d{2}$")
    regime: str = Field(min_length=2, max_length=20)
    effective_from: date
    note: str = Field(min_length=1, max_length=500)
    slabs: list[Slab] = Field(min_length=1)

class ParameterSet(BaseModel):
    financial_year: str = Field(pattern=r"^FY\d{4}-\d{2}$")
    regime: str = Field(min_length=2, max_length=20)
    effective_from: date
    note: str = Field(min_length=1, max_length=500)
    values: dict[str, Decimal]

class RateSet(BaseModel):
    effective_from: date
    note: str = Field(min_length=1, max_length=500)
    parameter: str = Field(min_length=1, max_length=80)
    value: Decimal
    unit: str = Field(min_length=1, max_length=50)

class ElectionSubmission(BaseModel):
    employee_id: str | None = Field(default=None, max_length=20)
    financial_year: str = Field(pattern=r"^FY\d{4}-\d{2}$")
    regime: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    election_date: date
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if self.election_date > self.effective_from:
            raise ValueError("election_date must not follow effective_from")
        return self

class DeclarationSubmission(BaseModel):
    employee_id: str | None = Field(default=None, max_length=20)
    financial_year: str = Field(pattern=r"^FY\d{4}-\d{2}$")
    deduction_code: str = Field(min_length=2, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    declared_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    supporting_document_reference: str | None = Field(default=None, max_length=500)

class ReviewDecision(BaseModel):
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    note: str | None = Field(default=None, max_length=500)

def _employee_for_submission(requested_id: str | None, actor: dict) -> str:
    if actor["role"] == "Employee":
        own_id = actor.get("employee_id")
        if not own_id or (requested_id and requested_id != own_id):
            raise HTTPException(403, "Employees may submit tax records only for their own linked account")
        return own_id
    if not requested_id:
        raise HTTPException(422, "employee_id is required for HR/Admin submissions")
    return requested_id

def _audit_tax_change(db: Session, employee_id: str, actor: dict, entity_type: str,
                      entity_id: str, action: str, details: dict) -> None:
    db.add(EmployeeTaxAuditEvent(event_id=uuid4().hex, employee_id=employee_id,
        actor_user_id=actor["user_id"], entity_type=entity_type, entity_id=entity_id,
        action=action, details=details, occurred_at=datetime.now(timezone.utc)))

def _election_dict(row: EmployeeTaxElection) -> dict:
    return {"election_id": row.election_id, "employee_id": row.employee_id,
        "financial_year": row.financial_year, "regime": row.regime,
        "election_date": row.election_date, "effective_from": row.effective_from,
        "effective_to": row.effective_to, "approval_status": row.approval_status,
        "submitted_at": row.submitted_at, "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at, "review_note": row.review_note}

def _declaration_dict(row: EmployeeTaxDeclaration) -> dict:
    return {"declaration_id": row.declaration_id, "employee_id": row.employee_id,
        "financial_year": row.financial_year, "deduction_code": row.deduction_code,
        "declared_amount": row.declared_amount,
        "supporting_document_reference": row.supporting_document_reference,
        "approval_status": row.approval_status, "submitted_at": row.submitted_at,
        "reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at,
        "review_note": row.review_note}

def _intervals_overlap(a_start: date, a_end: date | None,
                       b_start: date, b_end: date | None) -> bool:
    return (a_end is None or b_start <= a_end) and (b_end is None or a_start <= b_end)

def _require_non_sample(note: str):
    # Sample data remains readable/calculable for training, but API-created rows
    # must identify their approved source explicitly.
    if "sample" in note.casefold() or len(note.strip()) < 8:
        raise HTTPException(422, "Configuration note must identify an authoritative policy source; sample values are not accepted")

@router.get("/configuration")
def get_configuration(db: Session = Depends(get_db), _actor: dict = Depends(hr_actor)):
    return {
        "tax_slabs": [{"slab_id": r.slab_id, "financial_year": r.financial_year, "regime": r.regime,
            "lower_limit": r.income_from, "upper_limit": r.income_to, "tax_rate": r.rate_percent,
            "effective_from": r.effective_from, "effective_to": r.effective_to,
            "is_active": r.is_active, "note": r.note} for r in db.query(TaxSlab).order_by(
                TaxSlab.financial_year, TaxSlab.regime, TaxSlab.effective_from, TaxSlab.income_from).all()],
        "tax_parameters": [{"parameter": r.parameter, "financial_year": r.financial_year,
            "regime": r.regime, "value": r.value, "effective_from": r.effective_from,
            "effective_to": r.effective_to, "is_active": r.is_active, "note": r.note}
            for r in db.query(TaxParameter).order_by(TaxParameter.financial_year,
                TaxParameter.regime, TaxParameter.effective_from, TaxParameter.parameter).all()],
        "statutory_rates": [{"parameter": r.parameter, "value": r.value, "unit": r.unit,
            "effective_from": r.effective_from, "effective_to": r.effective_to,
            "is_active": r.is_active, "note": r.note}
            for r in db.query(StatutoryRate).order_by(StatutoryRate.parameter, StatutoryRate.effective_from).all()],
        "source_policy": "Existing CSV values are training samples, not authoritative payroll policy.",
    }

@router.post("/configuration/slabs", status_code=201)
def add_slab_configuration(payload: SlabSet, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    _require_non_sample(payload.note)
    rows = sorted(payload.slabs, key=lambda s: s.lower_limit)
    if rows[0].lower_limit != 0:
        raise HTTPException(422, "Tax slabs must begin at zero")
    for i, row in enumerate(rows):
        if row.upper_limit is not None and row.upper_limit <= row.lower_limit:
            raise HTTPException(422, "Slab upper limit must be greater than its lower limit")
        if i and (rows[i-1].upper_limit != row.lower_limit):
            raise HTTPException(422, "Tax slabs must be contiguous, ordered, and non-overlapping")
        if i == len(rows)-1 and row.upper_limit is not None:
            raise HTTPException(422, "Final tax slab must be open-ended")
    previous = db.query(TaxSlab).filter_by(financial_year=payload.financial_year,
        regime=payload.regime, is_active=True).order_by(TaxSlab.effective_from.desc()).first()
    if previous and payload.effective_from <= previous.effective_from:
        raise HTTPException(409, "New configuration must be effective after the existing configuration")
    ids = [f"TX-{uuid4().hex[:16].upper()}" for _ in rows]
    try:
        for slab_id, row in zip(ids, rows):
            db.add(TaxSlab(slab_id=slab_id, regime=payload.regime, financial_year=payload.financial_year,
                income_from=row.lower_limit, income_to=row.upper_limit, rate_percent=row.tax_rate,
                effective_from=payload.effective_from, effective_to=None, is_active=True,
                note=payload.note, created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        if previous:
            for old in db.query(TaxSlab).filter_by(financial_year=payload.financial_year,
                    regime=payload.regime, effective_from=previous.effective_from, is_active=True).all():
                old.effective_to = payload.effective_from - timedelta(days=1)
        db.commit()
    except Exception:
        db.rollback(); raise
    return {"financial_year": payload.financial_year, "regime": payload.regime,
        "effective_from": payload.effective_from, "slab_ids": ids}

@router.post("/configuration/parameters", status_code=201)
def add_tax_parameters(payload: ParameterSet, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    _require_non_sample(payload.note)
    required = {"standard_deduction", "rebate_threshold_taxable", "rebate_amount",
                "health_education_cess_percent"}
    if not required.issubset(payload.values) or any(v < 0 for v in payload.values.values()):
        raise HTTPException(422, "Provide non-negative standard deduction, rebate threshold, and cess values")
    if payload.values["health_education_cess_percent"] > 100:
        raise HTTPException(422, "Cess percentage cannot exceed 100")
    previous = db.query(TaxParameter).filter_by(financial_year=payload.financial_year,
        regime=payload.regime, is_active=True).order_by(TaxParameter.effective_from.desc()).first()
    if previous and payload.effective_from <= previous.effective_from:
        raise HTTPException(409, "New parameters must be effective after the existing configuration")
    try:
        if previous:
            old_rows = db.query(TaxParameter).filter_by(financial_year=payload.financial_year,
                regime=payload.regime, effective_from=previous.effective_from, is_active=True).all()
            for old in old_rows: old.effective_to = payload.effective_from - timedelta(days=1)
        for name, value in payload.values.items():
            db.add(TaxParameter(parameter=name, financial_year=payload.financial_year, regime=payload.regime,
                effective_from=payload.effective_from, effective_to=None, is_active=True, value=value,
                note=payload.note, created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        db.commit()
    except Exception:
        db.rollback(); raise
    return {"financial_year": payload.financial_year, "regime": payload.regime,
        "effective_from": payload.effective_from, "parameters": payload.values}

@router.post("/configuration/statutory-rates", status_code=201)
def add_statutory_rate(payload: RateSet, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    _require_non_sample(payload.note)
    if payload.value < 0 or (payload.unit.startswith("percent") and payload.value > 100):
        raise HTTPException(422, "Statutory rate is outside its valid range")
    previous = db.query(StatutoryRate).filter_by(parameter=payload.parameter,
        is_active=True).order_by(StatutoryRate.effective_from.desc()).first()
    if previous and payload.effective_from <= previous.effective_from:
        raise HTTPException(409, "New rate must be effective after the existing rate")
    try:
        if previous: previous.effective_to = payload.effective_from - timedelta(days=1)
        db.add(StatutoryRate(parameter=payload.parameter, effective_from=payload.effective_from,
            effective_to=None, is_active=True, value=payload.value, unit=payload.unit, note=payload.note,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        db.commit()
    except Exception:
        db.rollback(); raise
    return {"parameter": payload.parameter, "value": payload.value, "unit": payload.unit,
        "effective_from": payload.effective_from}

@router.post("/elections", status_code=201)
def submit_tax_election(payload: ElectionSubmission, db: Session = Depends(get_db),
                        actor: dict = Depends(current_actor)):
    employee_id = _employee_for_submission(payload.employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    existing = db.query(EmployeeTaxElection).filter(
        EmployeeTaxElection.employee_id == employee_id,
        EmployeeTaxElection.financial_year == payload.financial_year,
        EmployeeTaxElection.approval_status != "REJECTED").all()
    if any(_intervals_overlap(payload.effective_from, payload.effective_to,
                              row.effective_from, row.effective_to) for row in existing):
        raise HTTPException(409, "Election effective period overlaps an existing pending or approved election")
    row = EmployeeTaxElection(election_id=uuid4().hex, employee_id=employee_id,
        financial_year=payload.financial_year, regime=payload.regime.upper(),
        election_date=payload.election_date, effective_from=payload.effective_from,
        effective_to=payload.effective_to, approval_status="PENDING",
        submitted_at=datetime.now(timezone.utc))
    db.add(row)
    _audit_tax_change(db, employee_id, actor, "ELECTION", row.election_id, "SUBMITTED",
        {"financial_year": row.financial_year, "regime": row.regime,
         "effective_from": row.effective_from.isoformat(),
         "effective_to": row.effective_to.isoformat() if row.effective_to else None})
    db.commit()
    db.refresh(row)
    return _election_dict(row)

@router.get("/elections/{employee_id}")
def list_tax_elections(employee_id: str, db: Session = Depends(get_db),
                       actor: dict = Depends(current_actor)):
    require_employee_access(employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    return [_election_dict(row) for row in db.query(EmployeeTaxElection).filter_by(
        employee_id=employee_id).order_by(EmployeeTaxElection.financial_year,
        EmployeeTaxElection.effective_from, EmployeeTaxElection.submitted_at).all()]

@router.post("/elections/{election_id}/review")
def review_tax_election(election_id: str, payload: ReviewDecision,
                        db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    row = db.get(EmployeeTaxElection, election_id)
    if not row:
        raise HTTPException(404, "Tax election not found")
    if row.approval_status != "PENDING":
        raise HTTPException(409, "Only pending tax elections can be reviewed")
    if payload.decision == "APPROVED":
        others = db.query(EmployeeTaxElection).filter(
            EmployeeTaxElection.employee_id == row.employee_id,
            EmployeeTaxElection.financial_year == row.financial_year,
            EmployeeTaxElection.approval_status == "APPROVED",
            EmployeeTaxElection.election_id != row.election_id).all()
        if any(_intervals_overlap(row.effective_from, row.effective_to,
                                  other.effective_from, other.effective_to) for other in others):
            raise HTTPException(409, "An approved election already covers this effective period")
    row.approval_status = payload.decision
    row.reviewed_by = actor["user_id"]
    row.reviewed_at = datetime.now(timezone.utc)
    row.review_note = payload.note
    _audit_tax_change(db, row.employee_id, actor, "ELECTION", row.election_id, payload.decision,
        {"financial_year": row.financial_year, "regime": row.regime, "note": payload.note})
    db.commit()
    db.refresh(row)
    return _election_dict(row)

@router.post("/declarations", status_code=201)
def submit_tax_declaration(payload: DeclarationSubmission, db: Session = Depends(get_db),
                           actor: dict = Depends(current_actor)):
    employee_id = _employee_for_submission(payload.employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    code = payload.deduction_code.upper()
    duplicate = db.query(EmployeeTaxDeclaration).filter_by(employee_id=employee_id,
        financial_year=payload.financial_year, deduction_code=code).filter(
            EmployeeTaxDeclaration.approval_status != "REJECTED").first()
    if duplicate:
        raise HTTPException(409, "A pending or approved declaration already exists for this deduction code and year")
    row = EmployeeTaxDeclaration(declaration_id=uuid4().hex, employee_id=employee_id,
        financial_year=payload.financial_year, deduction_code=code,
        declared_amount=payload.declared_amount,
        supporting_document_reference=payload.supporting_document_reference,
        approval_status="PENDING", submitted_at=datetime.now(timezone.utc))
    db.add(row)
    _audit_tax_change(db, employee_id, actor, "DECLARATION", row.declaration_id, "SUBMITTED",
        {"financial_year": row.financial_year, "deduction_code": code,
         "declared_amount": format(payload.declared_amount, "f"),
         "has_supporting_document_reference": bool(payload.supporting_document_reference)})
    db.commit()
    db.refresh(row)
    return _declaration_dict(row)

@router.get("/declarations/{employee_id}")
def list_tax_declarations(employee_id: str, db: Session = Depends(get_db),
                          actor: dict = Depends(current_actor)):
    require_employee_access(employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    return [_declaration_dict(row) for row in db.query(EmployeeTaxDeclaration).filter_by(
        employee_id=employee_id).order_by(EmployeeTaxDeclaration.financial_year,
        EmployeeTaxDeclaration.deduction_code, EmployeeTaxDeclaration.submitted_at).all()]

@router.post("/declarations/{declaration_id}/review")
def review_tax_declaration(declaration_id: str, payload: ReviewDecision,
                           db: Session = Depends(get_db), actor: dict = Depends(hr_actor)):
    row = db.get(EmployeeTaxDeclaration, declaration_id)
    if not row:
        raise HTTPException(404, "Tax declaration not found")
    if row.approval_status != "PENDING":
        raise HTTPException(409, "Only pending tax declarations can be reviewed")
    row.approval_status = payload.decision
    row.reviewed_by = actor["user_id"]
    row.reviewed_at = datetime.now(timezone.utc)
    row.review_note = payload.note
    _audit_tax_change(db, row.employee_id, actor, "DECLARATION", row.declaration_id,
        payload.decision, {"financial_year": row.financial_year,
                           "deduction_code": row.deduction_code, "note": payload.note})
    db.commit()
    db.refresh(row)
    return _declaration_dict(row)

@router.get("/audit/{employee_id}")
def list_tax_audit(employee_id: str, db: Session = Depends(get_db),
                   actor: dict = Depends(current_actor)):
    require_employee_access(employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    return [{"event_id": row.event_id, "employee_id": row.employee_id,
             "actor_user_id": row.actor_user_id, "entity_type": row.entity_type,
             "entity_id": row.entity_id, "action": row.action,
             "details": row.details, "occurred_at": row.occurred_at}
            for row in db.query(EmployeeTaxAuditEvent).filter_by(employee_id=employee_id)
            .order_by(EmployeeTaxAuditEvent.occurred_at, EmployeeTaxAuditEvent.event_id).all()]
