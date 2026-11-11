"""Create a locally stored sample payslip from an imported payroll snapshot."""
import argparse
from pathlib import Path
from app.database import SessionLocal
from app.payslip_pdf import build_payslip_pdf
from app.payslip_service import get_payslip_data

def main():
    ap=argparse.ArgumentParser();ap.add_argument("employee_id");ap.add_argument("run_id");ap.add_argument("--output",default=None)
    args=ap.parse_args();target=Path(args.output) if args.output else Path("output/pdf")/f"sample-payslip-{args.employee_id}-{args.run_id}.pdf"
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise SystemExit(f"Refusing to overwrite {target}")
    with SessionLocal() as db:data=get_payslip_data(db,args.employee_id,args.run_id)
    target.write_bytes(build_payslip_pdf(data))
    print(f"Created {target} ({target.stat().st_size} bytes)")
if __name__=="__main__":main()
