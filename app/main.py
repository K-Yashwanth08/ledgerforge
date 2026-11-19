from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .routers import attendance, auth, departments, employees, expenses, invoices, ledger, leave, payroll, payslips, reports, roles, salaries, tax, users
from . import models  # register model metadata for Alembic
app = FastAPI(title="LedgerForge", version="1.0.0-rc1", description="Employee operations and payroll foundation")
app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "static"), name="assets")
@app.get("/health", tags=["system"])
def health(): return {"status": "ok", "service": "ledgerforge"}
@app.get("/api/v1/health", tags=["system"])
def versioned_health(): return health()
routers = (departments.router, auth.router, users.router, employees.router, roles.router,
           salaries.router, attendance.router, leave.router, payroll.router, payslips.router,
           ledger.router, invoices.router, reports.router, tax.router, expenses.router)
for route in routers:
    app.include_router(route, prefix="/api/v1")
    # Preserve already deployed clients while publishing the versioned API.
    app.include_router(route, include_in_schema=False)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
