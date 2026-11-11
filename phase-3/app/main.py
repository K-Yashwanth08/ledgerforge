from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .routers import attendance, auth, departments, employees, expenses, invoices, ledger, leave, payroll, payslips, reports, roles, salaries, tax, users
from . import models  # register model metadata for Alembic
app = FastAPI(title="LedgerForge", version="0.2.0", description="Employee operations and payroll foundation")
app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "static"), name="assets")
@app.get("/health", tags=["system"])
def health(): return {"status": "ok", "service": "ledgerforge"}
app.include_router(departments.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(employees.router)
app.include_router(roles.router)
app.include_router(salaries.router)
app.include_router(attendance.router)
app.include_router(leave.router)
app.include_router(payroll.router)
app.include_router(payslips.router)
app.include_router(ledger.router)
app.include_router(invoices.router)
app.include_router(reports.router)
app.include_router(tax.router)
app.include_router(expenses.router)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
