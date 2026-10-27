from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Employee, PayrollItem, PayrollRun
from ..payslip_pdf import build_payslip_pdf
from ..payslip_service import get_payslip_data
from ..schemas import PayslipRunOut
from ..security import current_actor

router=APIRouter(prefix="/payslips",tags=["payslips"])

def _authorize(employee_id: str, actor: dict):
    if actor["role"] not in {"hr","admin"} and actor["sub"] != employee_id:
        raise HTTPException(403,"You may retrieve only your own payslip")

@router.get("/employee/{employee_id}/runs", response_model=list[PayslipRunOut])
def available_payslip_runs(employee_id: str, db: Session = Depends(get_db), actor: dict = Depends(current_actor)):
    _authorize(employee_id, actor)
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    rows = db.query(PayrollRun, PayrollItem).join(PayrollItem, PayrollItem.run_id == PayrollRun.run_id).filter(
        PayrollItem.employee_id == employee_id
    ).order_by(PayrollRun.period_end.desc(), PayrollRun.run_id.desc()).all()
    return [{"run_id": run.run_id, "period_start": run.period_start, "period_end": run.period_end,
        "pay_date": run.pay_date, "gross_pay": item.gross_pay, "total_deductions": item.total_deductions,
        "net_pay": item.net_pay} for run, item in rows]

@router.get("/{employee_id}/{run_id}/data")
def payslip_data(employee_id: str,run_id: str,db: Session=Depends(get_db),actor: dict=Depends(current_actor)):
    _authorize(employee_id,actor)
    return get_payslip_data(db,employee_id,run_id)

@router.get("/{employee_id}/{run_id}")
def download_payslip(employee_id: str,run_id: str,db: Session=Depends(get_db),actor: dict=Depends(current_actor)):
    _authorize(employee_id,actor)
    data=get_payslip_data(db,employee_id,run_id)
    try: content=build_payslip_pdf(data)
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    return Response(content=content,media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="payslip-{employee_id}-{run_id}.pdf"'})
