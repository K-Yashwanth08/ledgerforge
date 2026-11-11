from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
from .routers import departments, employees, roles, salaries
from . import models  # register model metadata for Alembic
app = FastAPI(title="LedgerForge", version="0.2.0", description="Employee operations and payroll foundation")
@app.get("/health", tags=["system"])
def health(): return {"status": "ok", "service": "ledgerforge"}
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(roles.router)
app.include_router(salaries.router)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
